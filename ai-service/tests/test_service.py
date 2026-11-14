import pytest
from fastapi.testclient import TestClient
from app.main import app, Input, evidence, rag, valid_text, predict, estimate_cost

client=TestClient(app)
@pytest.mark.parametrize("mc",[101,102,103,104,105,106])
def test_all_input_source_ids(mc): assert Input(description="ремонт",mcId=mc).mcId==mc
@pytest.mark.parametrize("mc",[100,107,0,-1])
def test_invalid_source_ids(mc):
    with pytest.raises(ValueError):Input(description="ремонт",mcId=mc)
def test_string_source_id_rejected():
    with pytest.raises(ValueError):Input(description="ремонт",mcId="101")
@pytest.mark.parametrize("text,mc,expected",[
 ("Делаем ремонт квартиры под ключ",101,True),
 ("Комплексный ремонт квартиры",101,True),
 ("Ремонт квартиры под ключ не делаем",101,False),
 ("Делаю укладку плитки",103,True),("Монтаж розеток",105,True),("меняем трубы",104,True),
 ("штукатурка стен",102,True),("покраска стен",106,True),("плитку не укладываю",103,False),
 ("электрикой занимается другой подрядчик",105,False),("раньше делал сантехнику",104,False),
 ("ремонт квартиры под ключ",103,False),("использую штукатурку как материал",102,False),
 ("укладка плитки под ключ",103,True),("меняем смесители и ставим раковины",104,True),
 ("производим монтаж проводки и замену выключателей",105,True),("поклейка обоев и шпаклёвка",106,True),
 ("вопрос: какая цена у мастера по плитке",103,False),("обои🙂 клею",106,True),
 ("монтаж розеток; меняю выключатели",105,True),("плиточные работы\nделаю",103,True),
 ("укладываю керамогранит",103,True),("занимаюсь электромонтажом",105,True),
 ("сантехнические услуги",104,True),("трубы не меняю",104,False),
 ("другой подрядчик красит стены",106,False),("ремонт не делаю",101,False),
 ("покраска потолка",106,True),("штукатурные работы",102,True),
 ("установка унитаза",104,True),("прокладка кабеля",105,True),
 ("затирка швов",103,True),("снятие старых обоев",106,True)])
def test_evidence_scenarios(text,mc,expected): assert bool(evidence(text,mc)) is expected
def test_exact_evidence_offsets():
    s="🙂 Делаем укладку плитки!"; ev=evidence(s,103)[0]; assert s[ev["start"]:ev["end"]]==ev["text"]
@pytest.mark.parametrize("text,mc,expected",[
    ("Делаю плитку, но не штукатурю",103,True),
    ("Делаю плитку, но не штукатурю",102,False),
    ("Укладываю плитку и не занимаюсь сантехникой",103,True),
    ("Укладываю плитку и не занимаюсь сантехникой",104,False),
    ("Я делаю электрику, штукатурит другой подрядчик",105,True),
    ("Я делаю электрику, штукатурит другой подрядчик",102,False),
    ("Не укладываю плитку, но монтирую розетки",103,False),
    ("Не укладываю плитку, но монтирую розетки",105,True),
])
def test_evidence_scopes_negation_and_contractor(text,mc,expected):
    assert bool(evidence(text,mc)) is expected
def test_parse_target_ids_is_strict_and_excludes_source():
    from app.main import parse_target_ids
    assert parse_target_ids({"target_mcIds":[101,103,103]},101)==[103]
    for answer in ({"target_mcIds":["103"]},{"target_mcIds":[True]},{"target_mcIds":[999]},{}):
        with pytest.raises(RuntimeError):parse_target_ids(answer,101)
def test_deepseek_classifier_mode_is_wired(monkeypatch):
    import asyncio, app.main as service
    async def fake_deepseek(messages):return {"target_mcIds":[101,103]},{"prompt_tokens":2,"completion_tokens":2},"stop"
    monkeypatch.setattr(service,"deepseek",fake_deepseek);monkeypatch.setenv("CLASSIFIER_MODE","deepseek");monkeypatch.setenv("GENERATOR_PROVIDER","disabled")
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладка плитки','mcId':101})
    assert r.status_code==200 and r.json()=={'drafts':[{'mcId':103,'title':None,'text':None}]}
def test_deepseek_classifier_rejects_invalid_ids(monkeypatch):
    import asyncio, app.main as service
    async def fake_deepseek(messages):return {"target_mcIds":["103"]},None,"stop"
    monkeypatch.setattr(service,"deepseek",fake_deepseek);monkeypatch.setenv("CLASSIFIER_MODE","deepseek")
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладка плитки','mcId':101})
    assert r.status_code==503 and r.json()['error']['code']=='CLASSIFIER_UNAVAILABLE'
def test_official_json_live_shape():
    assert client.get('/health/live').json()=={'status':'live'}
def test_classify_missing_artifact_is_503(monkeypatch):
    import app.main as service
    monkeypatch.setattr(service,'MODEL',None)
    r=client.post('/internal/v1/avito/classify',json={'description':'Укладка плитки','mcId':101})
    assert r.status_code==503 and r.json()['error']['code']=='CLASSIFIER_UNAVAILABLE'
def test_end_to_end_contract_with_test_classifier(monkeypatch):
    import app.main as service
    class FakeClassifier:
        class_ids=(102,103,104,105,106)
        def predict_proba(self,items):return [[.05,.95,.02,.01,.02]]
    monkeypatch.setattr(service,'MODEL',{'model':FakeClassifier(),'class_ids':(102,103,104,105,106),'input_field':'description','threshold':.35,'version':'test-only'})
    monkeypatch.setenv('GENERATOR_PROVIDER','disabled')
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладка плитки под ключ.','mcId':101})
    assert r.status_code==200
    assert r.json()=={'drafts':[{'mcId':103,'title':None,'text':None}]}
    assert set(r.json())=={'drafts'}
def test_blank_input_rejected(): assert client.post('/internal/v1/avito/drafts',json={'description':' ','mcId':101}).status_code==422
def test_oversized_description_is_413(): assert client.post('/internal/v1/avito/drafts',json={'description':'x'*12001,'mcId':101}).status_code==413
def test_extra_output_fields_not_in_schema(): assert set(client.get('/health/live').json())=={'status'}
def test_forbidden_claim_guard(): assert valid_text('Кладём плитку',{'title':'Плитка','text':'Гарантия 5 лет'})==(None,None)
def test_no_unsupported_separate_claim(): assert valid_text('Монтаж плитки',{'title':'Плиточные работы','text':'Можно заказать отдельно'})==(None,None)
def test_unsupported_geography_guard(): assert valid_text('Укладываем плитку',{'title':'Плиточные работы','text':'Работаем в Москве'})==(None,None)
def test_numeric_claim_must_be_in_category_evidence(): assert valid_text('Укладка плитки. Цена от 5000 рублей относится к сантехнике.',{'title':'Плиточные работы','text':'Цена от 5000 рублей'},103)==(None,None)
def test_rag_empty_store_fallback(): assert rag(103,['укладка плитки'],'some text')==[]
def test_rag_category_and_verified_filter(tmp_path):
    import json
    p=tmp_path/'examples.jsonl'
    p.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in [
      {'example_id':'ok','mcId':103,'source_facts':'укладка плитки в ванной','approved_title':'Плиточные работы','approved_text':'Укладка плитки','verified':True,'origin':'human_reviewed_author'},
      {'example_id':'wrong-category','mcId':104,'source_facts':'укладка плитки','approved_title':'x','approved_text':'x','verified':True,'origin':'human_reviewed_author'},
      {'example_id':'unverified','mcId':103,'source_facts':'укладка плитки','approved_title':'x','approved_text':'x','verified':False,'origin':'human_reviewed_author'}]),encoding='utf8')
    assert [x['example_id'] for x in rag(103,['укладка плитки'],'совершенно другое',p)]==['ok']
def test_source_exclusion_and_dedup(monkeypatch):
    class M:
        classes_=[101,102,103,104,105,106]
        def predict_proba(self,x):return [[.9,.8,.7,.6,.5,.4]]
    assert 101 not in predict('x',101,M(),.3)
    assert predict('x',101,M(),.3)==[102,103,104,105,106]
def test_cost_unknown_when_no_price_profile(monkeypatch):
    monkeypatch.delenv('PRICE_INPUT_CACHE_MISS_USD_PER_M',raising=False); monkeypatch.delenv('PRICE_INPUT_CACHE_HIT_USD_PER_M',raising=False); monkeypatch.delenv('PRICE_OUTPUT_USD_PER_M',raising=False)
    assert estimate_cost({'prompt_tokens':10,'completion_tokens':5}) is None
def test_cost_uses_reported_cache_and_token_counts(monkeypatch):
    monkeypatch.setenv('PRICE_INPUT_CACHE_MISS_USD_PER_M','0.15'); monkeypatch.setenv('PRICE_INPUT_CACHE_HIT_USD_PER_M','0.003'); monkeypatch.setenv('PRICE_OUTPUT_USD_PER_M','0.6')
    assert estimate_cost({'prompt_tokens':100,'prompt_cache_hit_tokens':40,'prompt_cache_miss_tokens':60,'completion_tokens':20})==pytest.approx((40*.003+60*.15+20*.6)/1e6)
def test_deepseek_request_json_mode_and_limits(monkeypatch):
    import asyncio,app.main as service
    seen={}
    class Response:
        status_code=200
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':{'content':'{"ok":true}'},'finish_reason':'stop'}],'usage':{'prompt_tokens':3,'completion_tokens':2}}
    class Client:
        def __init__(self,**kw):seen['timeout']=kw['timeout']
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,headers,json):seen.update(url=url,headers=headers,payload=json);return Response()
    monkeypatch.setattr(service.httpx,'AsyncClient',Client); monkeypatch.setenv('DEEPSEEK_API_KEY','test-only'); monkeypatch.setenv('DEEPSEEK_MAX_OUTPUT_TOKENS','77')
    result,usage,finish=asyncio.run(service.deepseek([{'role':'system','content':'JSON'}]))
    assert result=={'ok':True} and usage['prompt_tokens']==3 and usage['completion_tokens']==2
    assert finish=='stop' and seen['payload']['max_tokens']==77 and seen['payload']['response_format']=={'type':'json_object'}
def test_deepseek_auth_failure_no_retry(monkeypatch):
    import asyncio,app.main as service
    seen={'calls':0}
    class Response:
        status_code=401
        def raise_for_status(self):raise service.httpx.HTTPStatusError('401',request=None,response=self)
    class Client:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kw):seen['calls']+=1;return Response()
    monkeypatch.setattr(service.httpx,'AsyncClient',Client);monkeypatch.setenv('DEEPSEEK_API_KEY','test-only');monkeypatch.setenv('DEEPSEEK_MAX_RETRIES','4')
    with pytest.raises(RuntimeError):asyncio.run(service.deepseek([{'role':'system','content':'JSON'}]))
    assert seen['calls']==1
def test_request_budget_blocks_before_http(monkeypatch):
    import asyncio,app.main as service
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-only');monkeypatch.setenv('PRICE_INPUT_CACHE_MISS_USD_PER_M','0.15');monkeypatch.setenv('PRICE_OUTPUT_USD_PER_M','0.6');monkeypatch.setenv('DEEPSEEK_MAX_OUTPUT_TOKENS','1200')
    token=service._REQUEST_BUDGET.set(1e-12)
    try:
        with pytest.raises(RuntimeError,match='REQUEST_BUDGET_EXCEEDED'):
            asyncio.run(service.deepseek([{'role':'system','content':'x'*2000}]))
    finally:service._REQUEST_BUDGET.reset(token)
def test_repair_failure_preserves_already_valid_draft(monkeypatch):
    import asyncio, app.main as service
    class FakeClassifier:
        class_ids=(102,103,104,105,106)
        def predict_proba(self,items):return [[.01,.95,.01,.95,.01]]
    async def fake_deepseek(messages):
        if "generate_v1" in messages[0]["content"] or "You create independent" in messages[0]["content"]:
            return {"drafts":[
                {"mcId":103,"title":"Плиточные работы","text":"Укладываю плитку"},
                {"mcId":105,"title":"Электрика","text":"Опыт 10 лет"}
            ]},{"prompt_tokens":20,"completion_tokens":20},"stop"
        raise RuntimeError("repair unavailable")
    monkeypatch.setattr(service,"MODEL",{"model":FakeClassifier(),"class_ids":FakeClassifier.class_ids,"input_field":"description","threshold":.35})
    monkeypatch.setattr(service,"deepseek",fake_deepseek)
    monkeypatch.setenv("GENERATOR_PROVIDER","deepseek")
    monkeypatch.setenv("CLASSIFIER_MODE","cpu")
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладываю плитку и монтирую розетки','mcId':101})
    assert r.status_code==200
    drafts={d['mcId']:d for d in r.json()['drafts']}
    assert drafts[103]['text']=='Укладываю плитку'
    assert drafts[105]['title'] is None and drafts[105]['text'] is None
@pytest.mark.parametrize("approved,expected",[(True,"Укладываю плитку"),(False,None)])
def test_optional_claim_verifier_fails_closed(monkeypatch,approved,expected):
    import asyncio, app.main as service
    class FakeClassifier:
        class_ids=(102,103,104,105,106)
        def predict_proba(self,items):return [[.01,.95,.01,.01,.01]]
    async def fake_deepseek(messages):
        if "You create independent" in messages[0]["content"]:
            return {"drafts":[{"mcId":103,"title":"Плиточные работы","text":"Укладываю плитку"}]},{"prompt_tokens":5,"completion_tokens":5},"stop"
        return {"drafts":[{"mcId":103,"approved":approved,"unsupported_claims":[],"wrong_category_claims":[]}]},{"prompt_tokens":5,"completion_tokens":5},"stop"
    monkeypatch.setattr(service,"MODEL",{"model":FakeClassifier(),"class_ids":FakeClassifier.class_ids,"input_field":"description","threshold":.35})
    monkeypatch.setattr(service,"deepseek",fake_deepseek)
    monkeypatch.setenv("GENERATOR_PROVIDER","deepseek");monkeypatch.setenv("CLASSIFIER_MODE","cpu");monkeypatch.setenv("CLAIM_VERIFIER_ENABLED","true")
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладываю плитку','mcId':101})
    assert r.status_code==200 and r.json()['drafts'][0]['text']==expected
