from __future__ import annotations
import json, os, re, time, uuid, logging, random
from contextvars import ContextVar
from pathlib import Path
import httpx, joblib
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT=Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT/".env")
except ImportError:pass
IDS=(101,102,103,104,105,106)
MAX_DESCRIPTION_CHARS=int(os.getenv("MAX_DESCRIPTION_CHARS","12000"))
NAMES={101:"Ремонт под ключ",102:"Штукатурные работы",103:"Плиточные работы",104:"Сантехника",105:"Электрика",106:"Поклейка обоев и малярные работы"}
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO")); logger=logging.getLogger("avito-ai")
_REQUEST_BUDGET:ContextVar[float|None]=ContextVar("request_budget_usd",default=None)
_PROVIDER_CALLS:ContextVar[int]=ContextVar("provider_http_calls",default=0)
class Input(BaseModel):
    model_config=ConfigDict(extra="forbid")
    description:str=Field(min_length=1,max_length=MAX_DESCRIPTION_CHARS)
    mcId:int=Field(strict=True)
    @field_validator("description")
    @classmethod
    def text_required(cls,v):
        if not v.strip(): raise ValueError("description must not be blank")
        return v
    @field_validator("mcId")
    @classmethod
    def category_allowed(cls,v):
        if v not in IDS: raise ValueError("mcId must be in 101..106")
        return v
class Draft(BaseModel):
    model_config=ConfigDict(extra="forbid")
    mcId:int=Field(strict=True)
    title:str|None=Field(max_length=255)
    text:str|None=Field(max_length=10000)
    @field_validator("mcId")
    @classmethod
    def valid_target(cls,v):
        if v not in IDS: raise ValueError("unknown mcId")
        return v
    @field_validator("title", "text")
    @classmethod
    def nonblank_when_present(cls,v):
        if v is not None and not v.strip(): raise ValueError("draft text must not be blank")
        return v
class Output(BaseModel):
    model_config=ConfigDict(extra="forbid")
    drafts:list[Draft]
    @field_validator("drafts")
    @classmethod
    def unique_categories(cls,v):
        ids=[x.mcId for x in v]
        if len(ids)!=len(set(ids)): raise ValueError("duplicate mcId")
        if any((x.title is None)!=(x.text is None) for x in v): raise ValueError("title/text must both be null or non-null")
        return v
def norm(s): return re.sub(r"\s+"," ",s.lower().replace("ё","е")).strip()
_ru=[chr(i) for i in range(0x430,0x450)]
_latin=list("abvgdezz iiklm noprstufhccssxyxeua".replace(" ",""))
_TRANS=str.maketrans({c:_latin[i] for i,c in enumerate(_ru)}|{chr(i):_latin[i-0x410] for i in range(0x410,0x430)}|{chr(0x451):"e",chr(0x401):"e"})
def latin(s):return s.lower().translate(_TRANS)
def get_model():
    p=Path(os.getenv("CPU_MODEL_PATH",str(ROOT/"artifacts/cpu_char.joblib")))
    if not p.exists(): return None
    data=joblib.load(p)
    if not isinstance(data,dict) or tuple(data.get("class_ids",()))!=(102,103,104,105,106) or data.get("input_field")!="description":
        raise RuntimeError("CPU_MODEL_INCOMPATIBLE")
    return data
def choose_local_classifier_backend(requested,transformer_path):
    value=(requested or "auto").strip().lower()
    if value=="auto":return "ensemble" if Path(transformer_path).is_dir() else "cpu"
    return value if value in {"cpu","ensemble","rubert"} else "cpu"
try:CPU_MODEL=get_model(); MODEL_LOAD_ERROR=None
except Exception:CPU_MODEL=None; MODEL_LOAD_ERROR="CPU_MODEL_LOAD_FAILED"; logger.error("CPU model artifact is missing or incompatible")
MODEL=CPU_MODEL
ACTIVE_BACKEND="cpu-charwb"
_rubert_path=os.getenv("RUBERT_MODEL_PATH",str(ROOT/"artifacts/rubert_base"))
_local_backend=choose_local_classifier_backend(os.getenv("LOCAL_CLASSIFIER_BACKEND","auto"),_rubert_path)
if _local_backend in {"rubert","ensemble"}:
    try:
        from app.transformer_classifier import ProbabilityBlend, RuBertClassifier
        _rubert=RuBertClassifier(_rubert_path)
        if _local_backend=="ensemble":
            if CPU_MODEL is None:raise RuntimeError("CPU_MODEL_UNAVAILABLE_FOR_ENSEMBLE")
            _classifier=ProbabilityBlend((CPU_MODEL["model"],_rubert),(.5,.5))
            _threshold=.475
        else:
            _classifier=_rubert
            _threshold=.475
        MODEL={"model":_classifier,"class_ids":(102,103,104,105,106),"input_field":"description","threshold":_threshold,"version":f"local-{_local_backend}-v1"}
        ACTIVE_BACKEND=f"{_local_backend}-{'cuda' if _rubert.device.type=='cuda' else 'cpu'}"
    except Exception as exc:
        if MODEL is None:MODEL_LOAD_ERROR="CLASSIFIER_UNAVAILABLE"
        logger.error("Optional local transformer could not load; using CPU fallback (%s)",type(exc).__name__)
        ACTIVE_BACKEND="cpu-fallback" if CPU_MODEL is not None else "unavailable"
def predict(text,source,model=None,threshold=.35):
    m=model if model is not None else MODEL
    if m is None: raise RuntimeError("CPU_MODEL_UNAVAILABLE")
    if isinstance(m,dict): clf=m["model"]; class_ids=m["class_ids"]; threshold=m["threshold"]
    else: clf=m; class_ids=getattr(m,"class_ids",(102,103,104,105,106))
    scores=clf.predict_proba([norm(text)])[0]
    return [mc for mc,s in zip(class_ids,scores) if s>=threshold and mc!=source and not explicitly_negated(text,mc)]
PATTERNS={
101:r"remont\w*.*pod\s+kluc|kompleksn\w* remont|kapitaln\w* remont",
102:r"stukatur\w*|oshtukatur\w*|vyravniv\w* sten",
103:r"plitk\w*|plitocn\w*|plitochn\w*|keramogranit\w*|mozaik\w*|zatirk\w*",
104:r"santehnik\w*|santehn\w*|santehnic\w*|trub\w*|smesitel\w*|rakovin\w*|unitaz\w*|kanaliz\w*|vodosnab\w*|sliv\w*",
105:r"elektr\w*|provodk\w*|kabel\w*|rozet\w*|vyklyuchatel\w*|elektromontazh\w*|osveshchen\w*|elektroset\w*",
106:r"obo\w*|pokras\w*|poklei\w*|shpaklev\w*|shpatlev\w*|malyar\w*|gruntov\w*|shlifovan\w*"}
NEG=r"(?:ne\s+(?:dela\w*|vypoln\w*|okazyv\w*|zanim\w*|bud\w*|predlag\w*|men\w*|menau\w*|uklad\w*|montir\w*|ustanav\w*|stukatur\w*|kle\w*|poklei\w*|spaklev\w*|spatlev\w*|slifov\w*|gruntov\w*|kras\w*)|ne\s+nashi|drug\w* podradcik|podradcik|podryadchik\s+ne\s+my|ran\w* delal|ran\w* zanim|bolshe\s+ne\s+(?:dela|prinima))"
EXCEPTION=r"(?:krome|iskluc\w*|za\s+iskluc\w*)"
EXCEPTION_FILLER=r"(?:vse\w*|rabot\w*|uslug\w*|remont\w*|po|uklad\w*|montaz\w*|ustanov\w*)"
def _parts(text):
    for clause in re.finditer(r"[^.!?;\n]+",text):
        raw=clause.group(); transformed=latin(raw)
        separators=list(re.finditer(r",|\b(?:i|no|a|zato|odnako|pri\s+etom)\b",transformed,re.I))
        cursor=0
        for sep in separators:
            yield clause.start()+cursor,clause.start()+sep.start(),raw[cursor:sep.start()],transformed[cursor:sep.start()]
            cursor=sep.end()
        yield clause.start()+cursor,clause.start()+len(raw),raw[cursor:],transformed[cursor:]

def _exception_spans(part,pat):
    pattern=rf"\b{EXCEPTION}\b\s+(?:(?:{EXCEPTION_FILLER})\s+){{0,3}}(?:{pat})"
    return [m.span() for m in re.finditer(pattern,part,re.I)]

def explicitly_negated(text,mc):
    """Return true only when every direct mention of a category is denied."""
    pat=PATTERNS.get(mc)
    if not pat:return False
    found=False
    for _,_,_,part in _parts(text):
        mentions=list(re.finditer(pat,part,re.I))
        if not mentions:continue
        found=True
        if re.search(NEG,part,re.I):continue
        excluded=_exception_spans(part,pat)
        if any(not any(left<=m.start() and m.end()<=right for left,right in excluded) for m in mentions):
            return False
    return found

def evidence(text,mc):
    result=[]; pat=PATTERNS.get(mc)
    if not pat:return result
    # Evaluate coordinated clauses independently so a negation or a different
    # contractor's work cannot cancel a supported service in the same sentence.
    for clause in re.finditer(r"[^.!?;\n]+",text):
        raw=clause.group(); base=clause.start(); transformed=latin(raw)
        separators=list(re.finditer(r",|\b(?:i|no|a|zato|odnako|pri\s+etom)\b",transformed,re.I))
        bounds=[]; cursor=0
        for sep in separators:
            bounds.append((cursor,sep.start())); cursor=sep.end()
        bounds.append((cursor,len(raw)))
        for left,right in bounds:
            while left<right and raw[left].isspace(): left+=1
            while right>left and raw[right-1].isspace(): right-=1
            if left>=right: continue
            start=base+left; end=base+right; part=transformed[left:right]
            matches=list(re.finditer(pat,part,re.I))
            if not matches:continue
            excluded=_exception_spans(part,pat)
            if not any(not any(left<=m.start() and m.end()<=right for left,right in excluded) for m in matches):continue
            if re.search(r"(?:^|\b)(?:vopros|sprashiv\w*|ishchu\s+mastera|nuzhen\s+master|ran\w*\s+delal|podradcik|podryadchik|ne\s+my|master\w*\s+po)(?:\b|$)",part,re.I):continue
            if re.search(NEG,part,re.I):continue
            if re.search(r"ispolzuy\w*.*kak\s+material|material\w*",part,re.I): continue
            result.append({"text":text[start:end],"start":start,"end":end})
    return result
def parse_target_ids(answer,source):
    if not isinstance(answer,dict) or not isinstance(answer.get("target_mcIds"),list):
        raise RuntimeError("DEEPSEEK_INVALID_CLASSIFICATION")
    ids=answer["target_mcIds"]
    if any(type(i) is not int or i not in IDS for i in ids):
        raise RuntimeError("DEEPSEEK_INVALID_CLASSIFICATION")
    return sorted({i for i in ids if i!=source},key=IDS.index)
def rag(mc,facts,current,path=None):
    p=Path(path) if path else ROOT/"data/curated_rag_examples.jsonl"
    if os.getenv("RAG_ENABLED","true").lower()!="true" or not p.exists():return []
    q=set(re.findall(r"\w+",norm(" ".join(facts)))); rows=[]
    for line in p.read_text(encoding="utf8").splitlines():
        x=json.loads(line)
        if x.get("verified") is not True or x.get("origin")!="human_reviewed_author" or x.get("mcId")!=mc or norm(x.get("source_facts",""))==norm(current):continue
        t=set(re.findall(r"\w+",norm(x["source_facts"]))); score=len(q&t)/max(1,len(q|t))
        cur=set(re.findall(r"\w+",norm(current)))
        if len(t&cur)/max(1,len(t|cur))>=.9:continue
        rows.append((score,x))
    rows.sort(key=lambda z:(-z[0],z[1]["example_id"]))
    return [{"example_id":x["example_id"],"score":round(s,4),"title":x["approved_title"],"text":x["approved_text"]} for s,x in rows[:int(os.getenv("RAG_TOP_K","2"))] if s>0]
async def deepseek(messages):
    key=os.getenv("DEEPSEEK_API_KEY")
    if not key:raise RuntimeError("DEEPSEEK_NOT_CONFIGURED")
    url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com").rstrip("/")+"/chat/completions"
    for attempt in range(int(os.getenv("DEEPSEEK_MAX_RETRIES","2"))+1):
        remaining=_REQUEST_BUDGET.get()
        if remaining is not None:
            cache=float(os.getenv("PRICE_INPUT_CACHE_MISS_USD_PER_M","0")); output=float(os.getenv("PRICE_OUTPUT_USD_PER_M","0"))
            if cache<=0 or output<=0:raise RuntimeError("BUDGET_PRICE_PROFILE_MISSING")
            chars=sum(len(str(m.get("content",""))) for m in messages)
            estimated=(chars*cache+int(os.getenv("DEEPSEEK_MAX_OUTPUT_TOKENS","1200"))*output)/1_000_000
            if estimated>remaining:raise RuntimeError("REQUEST_BUDGET_EXCEEDED")
            _REQUEST_BUDGET.set(remaining-estimated)
        try:
            async with httpx.AsyncClient(timeout=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS","30"))) as c:
                _PROVIDER_CALLS.set(_PROVIDER_CALLS.get()+1)
                r=await c.post(url,headers={"Authorization":"Bearer "+key},json={"model":os.getenv("DEEPSEEK_MODEL","deepseek-flash"),"messages":messages,"temperature":.2,"max_tokens":int(os.getenv("DEEPSEEK_MAX_OUTPUT_TOKENS","1200")),"response_format":{"type":"json_object"},"thinking":{"type":"enabled" if os.getenv("DEEPSEEK_THINKING","false").lower()=="true" else "disabled"}})
            if r.status_code in (401,403):raise RuntimeError("DEEPSEEK_AUTH_ERROR")
            r.raise_for_status(); d=r.json(); content=d["choices"][0]["message"]["content"]
            if not content.strip() or d["choices"][0].get("finish_reason")=="length":raise ValueError("EMPTY_OR_TRUNCATED")
            return json.loads(content),d.get("usage"),d["choices"][0].get("finish_reason")
        except RuntimeError:raise
        except httpx.HTTPStatusError as exc:
            retryable=exc.response.status_code in (429,500,502,503,504)
            if not retryable or attempt>=int(os.getenv("DEEPSEEK_MAX_RETRIES","2")):raise RuntimeError("DEEPSEEK_REQUEST_FAILED") from None
            await __import__("asyncio").sleep(min(.4*2**attempt+random.random()*.1,2))
        except (httpx.TransportError,ValueError,KeyError,json.JSONDecodeError):
            if attempt>=int(os.getenv("DEEPSEEK_MAX_RETRIES","2")):raise RuntimeError("DEEPSEEK_REQUEST_FAILED") from None
            await __import__("asyncio").sleep(min(.4*2**attempt+random.random()*.1,2))
def valid_text(description, generated, mc=None):
    title,text=generated.get("title"),generated.get("text")
    if not isinstance(title,str) or not isinstance(text,str) or not title.strip() or not text.strip():return None,None
    if len(title.strip())>255 or len(text.strip())>10000:return None,None
    target_evidence=" ".join(x["text"] for x in evidence(description,mc)) if mc is not None else description
    src=latin(norm(target_evidence)); out=latin(norm(title+" "+text))
    claim_patterns=(r"garant\w*",r"skidk\w*",r"opyt\w*\s+\d+",r"\d+\s+let\s+opyt\w*",r"vyezd\w*",r"zakaz\w*.*otdel\w*",r"mozhno\s+.*otdel\w*",r"cena\s+ot\s+\d+",r"stoimost\s+ot\s+\d+",r"litsenzi\w*",r"rabot\w*\s+(?:v|po)\s+\w+",r"srok\w*",r"\d+\s+(?:dney|nedel\w*|mesyac\w*)",r"segodnya|zavtra")
    for claim in claim_patterns:
        for match in re.finditer(claim,out,re.I):
            if not re.search(re.escape(match.group()),src,re.I):return None,None
    # Numeric claims are especially risky: every amount/year/quantity must occur in source.
    for n in re.findall(r"\d+(?:[.,]\d+)?",out):
        if n not in src:return None,None
    if mc in PATTERNS:
        for other,pattern in PATTERNS.items():
            if other!=mc and re.search(pattern,out,re.I) and not evidence(description,other):return None,None
        if not re.search(PATTERNS[mc],out,re.I):return None,None
    return title.strip(),text.strip()
def estimate_cost(usage):
    if not usage:return None
    try:
        miss_rate=os.getenv("PRICE_INPUT_CACHE_MISS_USD_PER_M"); hit_rate=os.getenv("PRICE_INPUT_CACHE_HIT_USD_PER_M"); out_rate=os.getenv("PRICE_OUTPUT_USD_PER_M")
        if not all((miss_rate,hit_rate,out_rate)):return None
        hit=usage.get("prompt_cache_hit_tokens")
        miss=usage.get("prompt_cache_miss_tokens")
        if hit is not None and miss is not None: inp=(hit*float(hit_rate)+miss*float(miss_rate))/1e6
        elif usage.get("prompt_tokens") is not None: inp=usage["prompt_tokens"]*float(miss_rate)/1e6
        else:return None
        out=usage.get("completion_tokens")
        return (inp+out*float(out_rate)/1e6) if out is not None else None
    except (ValueError,TypeError):return None
app=FastAPI(title="Avito AI",version="0.2.0")
@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    too_large=any(x.get("type")=="string_too_long" and "description" in x.get("loc",()) for x in exc.errors())
    return JSONResponse(status_code=413 if too_large else 422,content={"error":{"code":"TEXT_TOO_LARGE" if too_large else "INVALID_INPUT","message":"Description exceeds configured size" if too_large else "Request does not match the AI contract","requestId":getattr(request.state,"request_id",None)}})
@app.get("/health/live")
def live():return {"status":"live"}
@app.get("/health/ready")
def ready():
    ok=MODEL is not None
    return JSONResponse(status_code=200 if ok else 503,content={"status":"ready" if ok else "not_ready","classifier":ACTIVE_BACKEND if ok else (MODEL_LOAD_ERROR or "unavailable"),"generator":"deepseek-configured" if os.getenv("DEEPSEEK_API_KEY") else "degraded"})
@app.middleware("http")
async def protect_and_trace(request:Request,call_next):
    token=os.getenv("INTERNAL_API_TOKEN")
    if token and request.url.path.startswith("/internal/") and request.headers.get("Authorization")!="Bearer "+token:
        return JSONResponse(status_code=401,content={"error":{"code":"UNAUTHORIZED"}})
    request.state.request_id=request.headers.get("X-Request-ID",str(uuid.uuid4()))
    budget=os.getenv("MAX_REQUEST_USD")
    request_budget_token=_REQUEST_BUDGET.set(float(budget) if budget else None)
    calls_token=_PROVIDER_CALLS.set(0)
    try:
        response=await call_next(request); response.headers["X-Request-ID"]=request.state.request_id
        return response
    finally:
        _REQUEST_BUDGET.reset(request_budget_token); _PROVIDER_CALLS.reset(calls_token)
@app.post("/internal/v1/avito/classify",response_model=Output)
def classify(body:Input):
    try:ids=predict(body.description,body.mcId)
    except RuntimeError:return JSONResponse(status_code=503,content={"error":{"code":"CLASSIFIER_UNAVAILABLE"}})
    return {"drafts":[{"mcId":i,"title":None,"text":None} for i in ids]}
@app.post("/internal/v1/avito/drafts",response_model=Output)
async def create_drafts(body:Input,request:Request):
    rid=request.state.request_id; started=time.perf_counter(); t=time.perf_counter()
    mode=os.getenv("CLASSIFIER_MODE","cpu"); classification_calls=0; classification_usage=None; hybrid_fallback=False
    try:
        if mode=="cpu":targets=predict(body.description,body.mcId)
        elif mode=="deepseek":
            prompt=(ROOT/"app/prompts/classify_v1.txt").read_text(encoding="utf8")
            answer,classification_usage,_=await deepseek([{"role":"system","content":prompt},{"role":"user","content":json.dumps({"description":body.description,"source_mcId":body.mcId,"allowed_ids":list(IDS)},ensure_ascii=False)}]); classification_calls=1
            targets=parse_target_ids(answer,body.mcId)
        elif mode=="hybrid":
            targets=predict(body.description,body.mcId)
            if max(MODEL["model"].predict_proba([norm(body.description)])[0],default=1)<float(os.getenv("HYBRID_REVIEW_BELOW","0.55")):
                prompt=(ROOT/"app/prompts/classify_v1.txt").read_text(encoding="utf8")
                classification_calls=1
                try:
                    answer,classification_usage,_=await deepseek([{"role":"system","content":prompt},{"role":"user","content":json.dumps({"description":body.description,"source_mcId":body.mcId,"allowed_ids":list(IDS),"cpu_candidates":targets},ensure_ascii=False)}]); targets=parse_target_ids(answer,body.mcId)
                except Exception:hybrid_fallback=True
        else:return JSONResponse(status_code=500,content={"error":{"code":"INVALID_CLASSIFIER_MODE"}})
        targets=sorted({i for i in targets if type(i) is int and i in IDS and i!=body.mcId},key=IDS.index)
    except RuntimeError:return JSONResponse(status_code=503,content={"error":{"code":"CLASSIFIER_UNAVAILABLE"}})
    classification_ms=round((time.perf_counter()-t)*1000,2)
    if not targets:
        diag={"requestId":rid,"classifier":mode,"localModel":ACTIVE_BACKEND,"targetMcIds":[],"ragExampleIds":{},"timingsMs":{"classification":classification_ms,"total":round((time.perf_counter()-started)*1000,2)},"apiCalls":_PROVIDER_CALLS.get(),"usage":classification_usage,"estimatedCostUsd":estimate_cost(classification_usage),"priceProfile":os.getenv("PRICE_PROFILE"),"warnings":[]}
        app.state.diagnostics=getattr(app.state,"diagnostics",[])[-199:]+[diag]
        logger.info(json.dumps({k:v for k,v in diag.items() if k!="usage"},ensure_ascii=False))
        return {"drafts":[]}
    facts={i:evidence(body.description,i) for i in targets}; drafts=[]; rag_ids={}; usage=classification_usage; calls=classification_calls; warnings=["HYBRID_CPU_FALLBACK"] if hybrid_fallback else []
    entries=[]
    for i in targets:
        if not facts[i]:continue
        examples=rag(i,[x["text"] for x in facts[i]],body.description); rag_ids[str(i)]=[x["example_id"] for x in examples]
        entries.append({"mcId":i,"category":NAMES[i],"confirmed_services":[x["text"] for x in facts[i]],"evidence":facts[i],"rag_examples":examples})
    generated_ok=False
    try:
        prompt=(ROOT/"app/prompts/generate_v1.txt").read_text(encoding="utf8")
        if os.getenv("GENERATOR_PROVIDER","deepseek")=="deepseek" and entries:
            result,generation_usage,finish=await deepseek([{"role":"system","content":prompt},{"role":"user","content":json.dumps({"source_mcId":body.mcId,"targets":entries},ensure_ascii=False)}]); calls+=1; generated_ok=True
            if usage and generation_usage:usage={k:(usage.get(k,0) or 0)+(generation_usage.get(k,0) or 0) for k in set(usage)|set(generation_usage)}
            elif generation_usage:usage=generation_usage
            by_id={x.get("mcId"):x for x in result.get("drafts",[]) if isinstance(x,dict)}
            if finish=="length":by_id={}
        else:by_id={}
    except Exception:by_id={}; warnings.append("GENERATION_FAILED")
    # One bounded repair attempt applies only to invalid or missing drafts.
    invalid=[i for i in targets if i not in by_id or valid_text(body.description,by_id[i],i)==(None,None)]
    if invalid and generated_ok:
        try:
            repair=(ROOT/"app/prompts/repair_v1.txt").read_text(encoding="utf8")
            fixed,repair_usage,repair_finish=await deepseek([{"role":"system","content":repair},{"role":"user","content":json.dumps({"targets":[x for x in entries if x["mcId"] in invalid],"invalid_mcIds":invalid},ensure_ascii=False)}]); calls+=1
            if usage and repair_usage:
                usage={k:(usage.get(k,0) or 0)+(repair_usage.get(k,0) or 0) for k in set(usage)|set(repair_usage)}
            elif repair_usage:usage=repair_usage
            by_id.update({x.get("mcId"):x for x in fixed.get("drafts",[]) if isinstance(x,dict) and x.get("mcId") in invalid})
        except Exception:warnings.append("REPAIR_FAILED")
    candidates={i:valid_text(body.description,by_id.get(i,{}),i) if i in facts and facts[i] else (None,None) for i in targets}
    if os.getenv("CLAIM_VERIFIER_ENABLED","false").lower()=="true":
        reviewable=[{"mcId":i,"evidence":facts[i],"title":pair[0],"text":pair[1]} for i,pair in candidates.items() if pair[0] is not None]
        if reviewable:
            try:
                verifier_prompt=(ROOT/"app/prompts/verify_claims_v1.txt").read_text(encoding="utf8")
                review,review_usage,_=await deepseek([{"role":"system","content":verifier_prompt},{"role":"user","content":json.dumps({"source_description":body.description,"drafts":reviewable},ensure_ascii=False)}]); calls+=1
                if usage and review_usage:usage={k:(usage.get(k,0) or 0)+(review_usage.get(k,0) or 0) for k in set(usage)|set(review_usage)}
                elif review_usage:usage=review_usage
                reviewed=review.get("drafts") if isinstance(review,dict) else None
                if not isinstance(reviewed,list):raise ValueError("invalid verifier schema")
                by_review={x.get("mcId"):x for x in reviewed if isinstance(x,dict) and type(x.get("mcId")) is int}
                for i in reviewable:
                    item=by_review.get(i["mcId"])
                    approved=(isinstance(item,dict) and item.get("approved") is True and item.get("unsupported_claims")==[] and item.get("wrong_category_claims")==[])
                    if not approved:candidates[i["mcId"]]=(None,None);warnings.append(f"CLAIM_REJECTED_{i['mcId']}")
            except Exception:
                candidates={i:(None,None) for i in targets};warnings.append("CLAIM_VERIFICATION_FAILED")
    for i,(title,text) in candidates.items():
        if title is None:warnings.append(f"GENERATION_INVALID_{i}")
        drafts.append({"mcId":i,"title":title,"text":text})
    timing={"classification":classification_ms,"total":round((time.perf_counter()-started)*1000,2)}
    cost=estimate_cost(usage)
    diag={"requestId":rid,"classifier":mode,"localModel":ACTIVE_BACKEND,"generator":os.getenv("DEEPSEEK_MODEL","deepseek-flash"),"claimVerifier":"enabled" if os.getenv("CLAIM_VERIFIER_ENABLED","false").lower()=="true" else "disabled","targetMcIds":targets,"ragExampleIds":rag_ids,"timingsMs":timing,"apiCalls":_PROVIDER_CALLS.get(),"usage":usage,"estimatedCostUsd":cost,"priceProfile":os.getenv("PRICE_PROFILE"),"warnings":warnings}
    app.state.diagnostics=getattr(app.state,"diagnostics",[])[-199:]+[diag]
    logger.info(json.dumps(diag,ensure_ascii=False))
    return {"drafts":drafts}
@app.get("/internal/v1/avito/debug/last")
def debug_last(request:Request):
    return next((d for d in reversed(getattr(app.state,"diagnostics",[])) if d["requestId"]==request.headers.get("X-Request-ID")),{"status":"no_matching_request"})
@app.get("/internal/v1/avito/metrics")
def metrics():
    rows=getattr(app.state,"diagnostics",[]); totals=sorted(x["timingsMs"]["total"] for x in rows if "total" in x.get("timingsMs",{}))
    def percentile(p):return totals[min(len(totals)-1,int((len(totals)-1)*p))] if totals else None
    toks=[x["usage"].get("total_tokens") for x in rows if isinstance(x.get("usage"),dict) and isinstance(x["usage"].get("total_tokens"),(int,float))]
    return {"requests":len(rows),"latencyTotalMs":{"p50":percentile(.5),"p95":percentile(.95)},"tokenStats":{"measuredRequests":len(toks),"total":sum(toks) if toks else None},"costMeasuredRequests":sum(x.get("estimatedCostUsd") is not None for x in rows)}
