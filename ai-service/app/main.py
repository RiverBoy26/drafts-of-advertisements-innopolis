from __future__ import annotations
import asyncio, json, os, re, time, uuid, logging, random
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
_PROVIDER_METRICS:ContextVar[list|None]=ContextVar("provider_metrics",default=None)
class Input(BaseModel):
    model_config=ConfigDict(extra="forbid")
    description:str=Field(min_length=1,max_length=MAX_DESCRIPTION_CHARS)
    mcId:int=Field(strict=True)
    targetMcIds:list[int]|None=None
    @field_validator("targetMcIds",mode="before")
    @classmethod
    def known_targets(cls,v):
        if v is None:return v
        if not isinstance(v,list) or any(type(i) is not int or i not in range(102,107) for i in v) or len(v)!=len(set(v)):
            raise ValueError("targetMcIds must contain unique integers 102..106")
        return v
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
    default_model=ROOT/"artifacts/cpu_char_conflict_resolved.joblib"
    if not default_model.exists():default_model=ROOT/"artifacts/cpu_char_noise1024.joblib"
    if not default_model.exists():default_model=ROOT/"artifacts/cpu_char.joblib"
    p=Path(os.getenv("CPU_MODEL_PATH",str(default_model)))
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
_rubert_path=os.getenv("RUBERT_MODEL_PATH",str(ROOT/"artifacts/rubert_conflict_resolved"))
_local_backend=choose_local_classifier_backend(os.getenv("LOCAL_CLASSIFIER_BACKEND","auto"),_rubert_path)
if _local_backend in {"rubert","ensemble"}:
    try:
        from app.transformer_classifier import AdaptiveProbabilityBlend, ProbabilityBlend, RuBertClassifier
        _rubert=RuBertClassifier(_rubert_path)
        if _local_backend=="ensemble":
            if CPU_MODEL is None:raise RuntimeError("CPU_MODEL_UNAVAILABLE_FOR_ENSEMBLE")
            _rubert_weight=float(os.getenv("ENSEMBLE_RUBERT_WEIGHT","0.25"))
            _cpu_weight=float(os.getenv("ENSEMBLE_CPU_WEIGHT","0.75"))
            adaptive=os.getenv("ENSEMBLE_ADAPTIVE","false").lower() in {"1","true","yes","on"}
            if adaptive:
                _classifier=AdaptiveProbabilityBlend(
                    CPU_MODEL["model"], _rubert,
                    short_rubert_weight=float(os.getenv("ENSEMBLE_SHORT_RUBERT_WEIGHT","0.55")),
                    long_rubert_weight=float(os.getenv("ENSEMBLE_LONG_RUBERT_WEIGHT","0.45")),
                    token_limit=int(os.getenv("ENSEMBLE_ADAPTIVE_TOKEN_LIMIT","512")),
                )
            else:
                _classifier=ProbabilityBlend((CPU_MODEL["model"],_rubert),(_cpu_weight,_rubert_weight))
            _threshold=float(os.getenv("ENSEMBLE_THRESHOLD","0.525"))
        else:
            _classifier=_rubert
            _threshold=.475
        _version="conflict-resolved-adaptive-v1" if _local_backend=="ensemble" and adaptive else f"local-{_local_backend}-noise1024-v1"
        MODEL={"model":_classifier,"class_ids":(102,103,104,105,106),"input_field":"description","threshold":_threshold,"version":_version}
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
103:r"plitk\w*|plitocn\w*|plitochn\w*|keramogranit\w*|mozaik\w*|zatirk\w*|kafel\w*",
104:r"santehnik\w*|santehn\w*|santehnic\w*|trub\w*|smesitel\w*|rakovin\w*|unitaz\w*|kanaliz\w*|vodosnab\w*|sliv\w*",
105:r"elektr\w*|provodk\w*|kabel\w*|rozet\w*|vyklyuchatel\w*|elektromontazh\w*|osveshchen\w*|elektroset\w*",
106:r"obo\w*|kras\w*|pokras\w*|poklei\w*|spakl\w*|spatl\w*|shpakl\w*|shpatl\w*|malyar\w*|malar\w*|gruntov\w*|shlifovan\w*"}
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
        if mc==102 and re.search(r"gipsokarton\w*",transformed,re.I) and not re.search(r"stukatur\w*|oshtukatur\w*",transformed,re.I):continue
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
            if mc==102 and re.search(r"gipsokarton\w*",part,re.I) and not re.search(r"stukatur\w*|oshtukatur\w*",part,re.I):continue
            excluded=_exception_spans(part,pat)
            if not any(not any(left<=m.start() and m.end()<=right for left,right in excluded) for m in matches):continue
            if re.search(r"(?:^|\b)(?:vopros|sprashiv\w*|ishchu\s+mastera|nuzhen\s+master|ran\w*\s+delal|podradcik|podryadchik|ne\s+my|master\w*\s+po)(?:\b|$)",part,re.I):continue
            if re.search(NEG,part,re.I):continue
            if re.search(r"ispolzuy\w*.*kak\s+material|material\w*",part,re.I): continue
            result.append({"text":text[start:end],"start":start,"end":end})
    return result
def offered_service_text(description):
    """Exclude obvious search-keyword tails while preserving real service lists."""
    lines=[]
    for line in description.splitlines():
        if re.search(r"(?i)^\s*(?:🔎\s*)?(?:нас также ищут|поисковые запросы|ключевые слова)\s*[:：]?\s*$",line):
            break
        if line.count(",")>=10 and not re.search(r"(?i)\b(?:выполня\w*|дела\w*|укладыва\w*|монтир\w*|устанавлива\w*|покле\w*|крашу)\b",line):
            continue
        lines.append(line)
    return "\n".join(lines)
def target_offer_supported(description,mc):
    """A narrow sanity check for classifier-provided categories, not a classifier."""
    offered=offered_service_text(description)
    if mc==102 and not re.search(r"(?:штукатур\w*|оштукатур\w*)",norm(offered)):
        return False
    if mc==104:
        # Ceramic products and tiled utility cabinets are not plumbing work.
        offered=re.sub(r"(?i)сантех[- ]?шкаф\w*","",offered)
        offered="\n".join(line for line in offered.splitlines()
                          if not (re.search(r"(?i)изделия\s+из\s+керамогранита",line)
                                  and not re.search(r"(?i)установ\w*|монтаж\w*|подключ\w*",line)))
    return bool(evidence(offered,mc))
def shared_evidence(text):
    """Explicit provider-wide facts that can be reused without inventing category details."""
    result=[]
    general=r"\b(?:опыт\w*|стаж\w*|работаю\s+в|работаем\s+в|выезд\w*|фото\s+своих\s+работ|гаранти\w*|убираем\s+мусор|силами\s+одной\s+бригады|выполняем\s+все\s+работы\s+в\s+срок|рассчитаем\s+смету)\b"
    for match in re.finditer(r"[^.!?;\n]+",text):
        part=match.group().strip()
        if re.search(general,part,re.I):
            start=text.find(part,match.start(),match.end())
            result.append({"text":part,"start":start,"end":start+len(part)})
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
        try:x=json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed RAG entry")
            continue
        if not isinstance(x,dict) or x.get("verified") is not True or x.get("origin") not in {"human_reviewed_author","organizer_official_example"} or x.get("mcId")!=mc:continue
        if not all(isinstance(x.get(k),str) and x[k].strip() for k in ("example_id","source_facts","approved_title","approved_text")):continue
        if norm(x["source_facts"])==norm(current):continue
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
            call_started=time.perf_counter()
            async with httpx.AsyncClient(timeout=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS","30"))) as c:
                _PROVIDER_CALLS.set(_PROVIDER_CALLS.get()+1)
                r=await c.post(url,headers={"Authorization":"Bearer "+key},json={"model":os.getenv("DEEPSEEK_MODEL","deepseek-flash"),"messages":messages,"temperature":.2,"max_tokens":int(os.getenv("DEEPSEEK_MAX_OUTPUT_TOKENS","1200")),"response_format":{"type":"json_object"},"thinking":{"type":"enabled" if os.getenv("DEEPSEEK_THINKING","false").lower()=="true" else "disabled"}})
            if r.status_code in (401,403):raise RuntimeError("DEEPSEEK_AUTH_ERROR")
            r.raise_for_status(); d=r.json(); content=d["choices"][0]["message"]["content"]
            if not content.strip() or d["choices"][0].get("finish_reason")=="length":raise ValueError("EMPTY_OR_TRUNCATED")
            metrics=_PROVIDER_METRICS.get()
            if metrics is not None:
                metrics.append({"durationMs":round((time.perf_counter()-call_started)*1000,2),"usage":d.get("usage"),"estimatedCostUsd":estimate_cost(d.get("usage"))})
            return json.loads(content),d.get("usage"),d["choices"][0].get("finish_reason")
        except RuntimeError:raise
        except httpx.HTTPStatusError as exc:
            retryable=exc.response.status_code in (429,500,502,503,504)
            if not retryable or attempt>=int(os.getenv("DEEPSEEK_MAX_RETRIES","2")):raise RuntimeError("DEEPSEEK_REQUEST_FAILED") from None
            await __import__("asyncio").sleep(min(.4*2**attempt+random.random()*.1,2))
        except (httpx.TransportError,ValueError,KeyError,json.JSONDecodeError):
            if attempt>=int(os.getenv("DEEPSEEK_MAX_RETRIES","2")):raise RuntimeError("DEEPSEEK_REQUEST_FAILED") from None
            await __import__("asyncio").sleep(min(.4*2**attempt+random.random()*.1,2))
async def deepseek_categories(messages, per_category=False):
    """Generate in one call; split only targeted repairs and account for each call."""
    payload=json.loads(messages[1]["content"])
    field="targets" if "targets" in payload else "drafts"
    items=payload.get(field,[])
    if len(items)<=1 or (os.getenv("GENERATION_REQUEST_MODE","batch")=="batch" and not per_category):
        return await deepseek(messages)
    semaphore=asyncio.Semaphore(max(1,min(5,int(os.getenv("GENERATION_CONCURRENCY","5")))))
    remaining=_REQUEST_BUDGET.get()
    async def one(item):
        child={**payload,field:[item]}
        if "invalid_mcIds" in child:child["invalid_mcIds"]=[item["mcId"]]
        if "rejected_drafts" in child:child["rejected_drafts"]=[d for d in child["rejected_drafts"] if d["mcId"]==item["mcId"]]
        if "previous_rejections" in child:child["previous_rejections"]=[d for d in child["previous_rejections"] if d["mcId"]==item["mcId"]]
        budget_token=_REQUEST_BUDGET.set(remaining/len(items) if remaining is not None else None)
        calls_token=_PROVIDER_CALLS.set(0)
        usage=None
        try:
            async with semaphore:
                result,usage,finish=await deepseek([messages[0],{"role":"user","content":json.dumps(child,ensure_ascii=False)}])
            records=result.get("drafts") if isinstance(result,dict) else None
            if not isinstance(records,list) or len(records)!=1 or not isinstance(records[0],dict) or type(records[0].get("mcId")) is not int or records[0]["mcId"]!=item["mcId"]:
                raise ValueError("category response mismatch")
            if field=="targets":Output.model_validate({"drafts":records})
            elif type(records[0].get("approved")) is not bool or not isinstance(records[0].get("unsupported_claims"),list) or not isinstance(records[0].get("wrong_category_claims"),list):
                raise ValueError("invalid category verification")
            return records,usage,_PROVIDER_CALLS.get(),_REQUEST_BUDGET.get()
        except Exception:
            failed={"mcId":item["mcId"],"title":None,"text":None} if field=="targets" else {"mcId":item["mcId"],"approved":False,"unsupported_claims":["Verification failed; retry required"],"wrong_category_claims":[]}
            return [failed],usage,_PROVIDER_CALLS.get(),_REQUEST_BUDGET.get()
        finally:
            _REQUEST_BUDGET.reset(budget_token);_PROVIDER_CALLS.reset(calls_token)
    results=await asyncio.gather(*(one(item) for item in items))
    usage=None;drafts=[]
    for records,tokens,_,_ in results:
        drafts.extend(records);usage=combine_usage(usage,tokens)
    _PROVIDER_CALLS.set(_PROVIDER_CALLS.get()+sum(r[2] for r in results))
    if remaining is not None:_REQUEST_BUDGET.set(sum(r[3] for r in results))
    return {"drafts":drafts},usage,"stop"

def valid_text(description, generated, mc=None, semantic=False):
    title,text=generated.get("title"),generated.get("text")
    if not isinstance(title,str) or not isinstance(text,str) or not title.strip() or not text.strip():return None,None
    if len(title.strip())>255 or len(text.strip())>10000:return None,None
    if semantic:
        # Narrow regression checks supplement the semantic guard; category IDs
        # alone never prove a service or authorize a more specific operation.
        plaster=r"(?:штукатур\w*|оштукатур\w*)"
        if mc==102:
            if not re.search(plaster,norm(description)) or not re.search(plaster,norm(text)):
                return None,None
        if mc==106 and re.search(plaster,norm(title+" "+text)):
            return None,None
        # Meaning, scope, numbers and shared conditions are checked against the
        # full source by the mandatory semantic guard, not substring rules.
        sentences=[norm(x) for x in re.split(r"[.!?\n]+",text) if len(x.strip())>15]
        if len(sentences)!=len(set(sentences)):return None,None
        source_numbers=set(re.findall(r"\d+(?:[.,]\d+)?",description))
        if any(n not in source_numbers for n in re.findall(r"\d+(?:[.,]\d+)?",title+" "+text)):return None,None
        return title.strip(),text.strip()
    if re.search(r"\b([а-яёa-z]{5,})\b(?:\W+\w+){0,2}\W+\1\b",norm(text),re.I):return None,None
    target_evidence=" ".join(x["text"] for x in evidence(description,mc)+shared_evidence(description)) if mc is not None else description
    src=latin(norm(target_evidence)); out=latin(norm(title+" "+text))
    claim_patterns=((r"garant\w*",r"garant\w*"),(r"skidk\w*",r"skidk\w*"),(r"opyt\w*\s+\d+",r"opyt\w*|stazh\w*"),(r"\d+\s+let\s+opyt\w*",r"opyt\w*|stazh\w*"),(r"vyezd\w*",r"vyezd\w*"),(r"zakaz\w*.*otdel\w*",r"otdel\w*"),(r"mozhno\s+.*otdel\w*",r"otdel\w*"),(r"cena\s+ot\s+\d+",r"cena\s+ot\s+\d+"),(r"stoimost\s+ot\s+\d+",r"stoimost\s+ot\s+\d+"),(r"litsenzi\w*",r"litsenzi\w*"),(r"srok\w*",r"srok\w*"),(r"\d+\s+(?:dney|nedel\w*|mesyac\w*)",r"\d+\s+(?:dney|nedel\w*|mesyac\w*)"),(r"segodnya|zavtra",r"segodnya|zavtra"))
    for claim,support in claim_patterns:
        if re.search(claim,out,re.I) and not re.search(support,src,re.I):return None,None
    for match in re.finditer(r"rabot\w*\s+(?:v|po)\s+\w+",out,re.I):
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
def combine_usage(first,second):
    if not first:return second
    if not second:return first
    return {key:(first.get(key,0) or 0)+(second.get(key,0) or 0)
            for key in set(first)|set(second)
            if isinstance(first.get(key,0),(int,float)) and isinstance(second.get(key,0),(int,float))}
def parsed_drafts(result,targets):
    validated=Output.model_validate(result)
    if {d.mcId for d in validated.drafts} != set(targets):raise ValueError("missing or unexpected target")
    return {d.mcId:d.model_dump() for d in validated.drafts}
def presentation_style(description):
    emojis=list(dict.fromkeys(re.findall(r"[\U0001F300-\U0001FAFF✅🔹]",description)))
    return {"source_has_emojis":bool(emojis),"source_emoji_examples":emojis[:3],
            "source_has_bullet_list":bool(re.search(r"(?m)^\s*(?:[•\-✅🔹]|\d+[.)])\s*\S",description))}
app=FastAPI(title="Avito AI",version="0.2.0")
@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    too_large=any(x.get("type")=="string_too_long" and "description" in x.get("loc",()) for x in exc.errors())
    return JSONResponse(status_code=413 if too_large else 422,content={"error":{"code":"TEXT_TOO_LARGE" if too_large else "INVALID_INPUT","message":"Description exceeds configured size" if too_large else "Request does not match the AI contract","requestId":getattr(request.state,"request_id",None)}})
@app.get("/health/live")
def live():return {"status":"live"}
@app.get("/health/ready")
def ready():
    evidence_mode=os.getenv("CLASSIFIER_MODE","cpu")=="evidence"
    ok=evidence_mode or MODEL is not None
    return JSONResponse(status_code=200 if ok else 503,content={"status":"ready" if ok else "not_ready","classifier":"evidence" if evidence_mode else (ACTIVE_BACKEND if ok else (MODEL_LOAD_ERROR or "unavailable")),"generator":"deepseek-configured" if os.getenv("DEEPSEEK_API_KEY") else "degraded"})
@app.middleware("http")
async def protect_and_trace(request:Request,call_next):
    token=os.getenv("INTERNAL_API_TOKEN")
    if token and request.url.path.startswith("/internal/") and request.headers.get("Authorization")!="Bearer "+token:
        return JSONResponse(status_code=401,content={"error":{"code":"UNAUTHORIZED"}})
    request.state.request_id=request.headers.get("X-Request-ID",str(uuid.uuid4()))
    budget=os.getenv("MAX_REQUEST_USD")
    request_budget_token=_REQUEST_BUDGET.set(float(budget) if budget else None)
    calls_token=_PROVIDER_CALLS.set(0)
    metrics_token=_PROVIDER_METRICS.set([])
    try:
        response=await call_next(request); response.headers["X-Request-ID"]=request.state.request_id
        return response
    finally:
        _REQUEST_BUDGET.reset(request_budget_token); _PROVIDER_CALLS.reset(calls_token); _PROVIDER_METRICS.reset(metrics_token)
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
        if body.targetMcIds is not None:
            if body.mcId!=101:return JSONResponse(status_code=422,content={"error":{"code":"SOURCE_MC_ID_MUST_BE_101"}})
            targets=body.targetMcIds; mode="provided"
        elif mode=="cpu":targets=predict(body.description,body.mcId)
        elif mode=="evidence":
            if body.mcId!=101:return JSONResponse(status_code=422,content={"error":{"code":"SOURCE_MC_ID_MUST_BE_101"}})
            targets=[i for i in IDS if i!=101 and evidence(body.description,i)]
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
        diag={"requestId":rid,"classifier":mode,"localModel":ACTIVE_BACKEND,"targetMcIds":[],"ragExampleIds":{},"timingsMs":{"classification":classification_ms,"total":round((time.perf_counter()-started)*1000,2)},"apiCalls":_PROVIDER_CALLS.get(),"providerCalls":_PROVIDER_METRICS.get(),"usage":classification_usage,"estimatedCostUsd":estimate_cost(classification_usage),"priceProfile":os.getenv("PRICE_PROFILE"),"warnings":[]}
        app.state.diagnostics=getattr(app.state,"diagnostics",[])[-199:]+[diag]
        logger.info(json.dumps({k:v for k,v in diag.items() if k!="usage"},ensure_ascii=False))
        return {"drafts":[]}
    # Classifier-provided labels are candidates; do not spend provider calls
    # on categories with no service evidence in the author's offer.
    unsupported_target_ids=[i for i in targets if not target_offer_supported(body.description,i)]
    generation_targets=[i for i in targets if i not in unsupported_target_ids]
    facts={i:evidence(body.description,i) for i in generation_targets}; drafts=[]; rag_ids={}; usage=classification_usage; calls=classification_calls; warnings=["HYBRID_CPU_FALLBACK"] if hybrid_fallback else []
    warnings.extend(f"TARGET_UNSUPPORTED_{i}" for i in unsupported_target_ids)
    entries=[]
    for i in generation_targets:
        examples=rag(i,[x["text"] for x in facts[i]],body.description); rag_ids[str(i)]=[x["example_id"] for x in examples]
        entries.append({"mcId":i,"category":NAMES[i],"source_service_hints":[x["text"] for x in facts[i]],"evidence":facts[i],"shared_evidence":shared_evidence(body.description),"rag_examples":examples})
    generated_ok=False
    try:
        prompt=(ROOT/"app/prompts/generate_v1.txt").read_text(encoding="utf8")
        if os.getenv("GENERATOR_PROVIDER","deepseek")=="deepseek" and entries:
            result,generation_usage,finish=await deepseek_categories([{"role":"system","content":prompt},{"role":"user","content":json.dumps({"source_mcId":body.mcId,"source_description":body.description,"presentation":presentation_style(body.description),"targets":entries},ensure_ascii=False)}]); calls+=1; generated_ok=True
            usage=combine_usage(usage,generation_usage)
            by_id=parsed_drafts(result,generation_targets)
            if finish=="length":by_id={}
        else:by_id={}
    except Exception:by_id={}; warnings.append("GENERATION_FAILED")
    # One bounded repair attempt applies only to invalid or missing drafts.
    invalid=[i for i in generation_targets if i not in by_id or valid_text(body.description,by_id[i],i,semantic=True)==(None,None)]
    for _ in range(max(0,min(3,int(os.getenv("GUARDRAIL_RETRY_ATTEMPTS","2"))))):
        if not invalid or not generated_ok:break
        try:
            repair=(ROOT/"app/prompts/repair_v1.txt").read_text(encoding="utf8")
            fixed,repair_usage,repair_finish=await deepseek_categories([{"role":"system","content":repair},{"role":"user","content":json.dumps({"source_description":body.description,"presentation":presentation_style(body.description),"targets":[x for x in entries if x["mcId"] in invalid],"invalid_mcIds":invalid,"validation_feedback":"Missing, null or structurally invalid draft. Re-read the full source, including named specialists in the team. Generate a short supported description; do not invent services."},ensure_ascii=False)}],per_category=True); calls+=1
            usage=combine_usage(usage,repair_usage)
            by_id.update(parsed_drafts(fixed,invalid))
        except Exception:warnings.append("REPAIR_FAILED")
        invalid=[i for i in invalid if valid_text(body.description,by_id.get(i,{}),i,semantic=True)==(None,None)]
    candidates={i:valid_text(body.description,by_id.get(i,{}),i,semantic=True) for i in generation_targets}
    guardrail_regeneration_attempts=0; guardrail_recovered=[]
    verify_enabled=os.getenv("GENERATOR_PROVIDER","deepseek")=="deepseek" and (mode=="provided" or os.getenv("CLAIM_VERIFIER_ENABLED","false").lower()=="true")
    if verify_enabled:
        reviewable=[{"mcId":i,"category":NAMES[i],"title":pair[0],"text":pair[1]} for i,pair in candidates.items() if pair[0] is not None]
        if reviewable:
            review_validated=False
            try:
                verifier_prompt=(ROOT/"app/prompts/verify_claims_v1.txt").read_text(encoding="utf8")
                review,review_usage,_=await deepseek_categories([{"role":"system","content":verifier_prompt},{"role":"user","content":json.dumps({"source_description":body.description,"drafts":reviewable},ensure_ascii=False)}]); calls+=1
                usage=combine_usage(usage,review_usage)
                reviewed=review.get("drafts") if isinstance(review,dict) else None
                if not isinstance(reviewed,list):raise ValueError("invalid verifier schema")
                if len(reviewed)!=len(reviewable) or any(not isinstance(x,dict) or type(x.get('mcId')) is not int for x in reviewed) or {x['mcId'] for x in reviewed}!={x['mcId'] for x in reviewable}:raise ValueError("verifier target mismatch")
                review_validated=True
                by_review={x.get("mcId"):x for x in reviewed if isinstance(x,dict) and type(x.get("mcId")) is int}
                rejected=[]
                for i in reviewable:
                    item=by_review.get(i["mcId"])
                    approved=(isinstance(item,dict) and item.get("approved") is True and item.get("unsupported_claims")==[] and item.get("wrong_category_claims")==[])
                    if not approved:
                        rejected.append({**i,"review":item})
                        candidates[i["mcId"]]=(None,None);warnings.append(f"CLAIM_REJECTED_{i['mcId']}")
                max_regenerations=max(0,min(3,int(os.getenv("GUARDRAIL_RETRY_ATTEMPTS","2"))))
                original_rejections=list(rejected)
                repair=(ROOT/"app/prompts/repair_v1.txt").read_text(encoding="utf8")
                for _ in range(max_regenerations):
                    if not rejected:break
                    guardrail_regeneration_attempts+=1
                    pending_ids={d['mcId'] for d in rejected}
                    fixed,u,_=await deepseek_categories([{"role":"system","content":repair},{"role":"user","content":json.dumps({"source_description":body.description,"presentation":presentation_style(body.description),"targets":[x for x in entries if x['mcId'] in pending_ids],"invalid_mcIds":sorted(pending_ids),"rejected_drafts":rejected},ensure_ascii=False)}],per_category=True)
                    usage=combine_usage(usage,u)
                    replacements=[]; next_rejected=[]
                    for item in parsed_drafts(fixed,pending_ids).values():
                        pair=valid_text(body.description,item,item['mcId'],semantic=True)
                        if pair[0]:replacements.append({"mcId":item['mcId'],"category":NAMES[item['mcId']],"title":pair[0],"text":pair[1]})
                    replacement_ids={item['mcId'] for item in replacements}
                    for old in rejected:
                        if old['mcId'] not in replacement_ids:
                            next_rejected.append({**old,"review":{"approved":False,"unsupported_claims":["Повторная генерация не дала корректного текста для этой категории"],"wrong_category_claims":[]}})
                    if replacements:
                        final_review,u,_=await deepseek_categories([{"role":"system","content":verifier_prompt},{"role":"user","content":json.dumps({"source_description":body.description,"drafts":replacements,"previous_rejections":[x for x in original_rejections if x['mcId'] in replacement_ids]},ensure_ascii=False)}])
                        usage=combine_usage(usage,u)
                        reviewed_again=final_review.get('drafts') if isinstance(final_review,dict) else None
                        if not isinstance(reviewed_again,list) or len(reviewed_again)!=len(replacements) or any(not isinstance(x,dict) or type(x.get('mcId')) is not int for x in reviewed_again) or {x['mcId'] for x in reviewed_again}!={x['mcId'] for x in replacements}:
                            raise ValueError("verifier target mismatch")
                        by_final={x['mcId']:x for x in reviewed_again}
                        for item in replacements:
                            verdict=by_final[item['mcId']]
                            if verdict.get('approved') is True and verdict.get('unsupported_claims')==[] and verdict.get('wrong_category_claims')==[]:
                                candidates[item['mcId']]=(item['title'],item['text']);guardrail_recovered.append(item['mcId'])
                            else:
                                next_rejected.append({**item,"review":verdict})
                    rejected=next_rejected
            except Exception:
                if not review_validated:candidates={i:(None,None) for i in generation_targets}
                warnings.append("CLAIM_REPAIR_FAILED" if review_validated else "CLAIM_VERIFICATION_FAILED")
    for i,(title,text) in candidates.items():
        if title is None and i not in unsupported_target_ids:warnings.append(f"GENERATION_INVALID_{i}")
        drafts.append({"mcId":i,"title":title,"text":text})
    timing={"classification":classification_ms,"total":round((time.perf_counter()-started)*1000,2)}
    cost=estimate_cost(usage)
    diag={"requestId":rid,"classifier":mode,"localModel":ACTIVE_BACKEND,"generator":os.getenv("DEEPSEEK_MODEL","deepseek-flash"),"claimVerifier":"enabled" if verify_enabled else "disabled","guardrailRegenerationAttempts":guardrail_regeneration_attempts,"guardrailRecoveredMcIds":sorted(set(guardrail_recovered)),"targetMcIds":targets,"acceptedTargetMcIds":generation_targets,"unsupportedTargetMcIds":unsupported_target_ids,"ragExampleIds":rag_ids,"timingsMs":timing,"apiCalls":_PROVIDER_CALLS.get(),"providerCalls":_PROVIDER_METRICS.get(),"usage":usage,"estimatedCostUsd":cost,"priceProfile":os.getenv("PRICE_PROFILE"),"warnings":warnings}
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
