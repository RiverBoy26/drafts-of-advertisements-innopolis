import pytest
from fastapi.testclient import TestClient
from app.main import app, Input, evidence, rag, valid_text, predict, estimate_cost

client=TestClient(app)
def test_semantic_repair_failure_preserves_approved_sibling(monkeypatch):
    monkeypatch.setenv("GENERATION_REQUEST_MODE","batch")
    import app.main as service
    monkeypatch.setenv('GENERATOR_PROVIDER','deepseek')
    calls=[]
    async def fake(messages):
        calls.append(messages)
        if len(calls)==1:return {'drafts':[{'mcId':103,'title':'Плитка','text':'Укладываю плитку.'},{'mcId':105,'title':'Электрика','text':'Монтирую розетки.'}]},None,'stop'
        if len(calls)==2:
            payload=__import__('json').loads(messages[1]['content'])
            assert payload['drafts'][1]['category']=='Электрика'
            return {'drafts':[{'mcId':103,'approved':True,'unsupported_claims':[],'wrong_category_claims':[]},{'mcId':105,'approved':False,'unsupported_claims':['исправить'],'wrong_category_claims':[]}]},None,'stop'
        raise RuntimeError('repair unavailable')
    monkeypatch.setattr(service,'deepseek',fake)
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладываю плитку и монтирую розетки.','mcId':101,'targetMcIds':[103,105]})
    assert r.status_code==200
    assert r.json()['drafts'][0]['text']=='Укладываю плитку.'
    assert r.json()['drafts'][1]['text'] is None
def test_guardrail_regenerates_rejected_category_twice_with_feedback(monkeypatch):
    monkeypatch.setenv("GENERATION_REQUEST_MODE","batch")
    import json, app.main as service
    monkeypatch.setenv('GENERATOR_PROVIDER','deepseek')
    monkeypatch.setenv('GUARDRAIL_RETRY_ATTEMPTS','2')
    calls=[]
    async def fake(messages):
        calls.append(messages)
        number=len(calls)
        if number==1:
            return {'drafts':[{'mcId':103,'title':'Плитка','text':'Укладываю плитку.'},{'mcId':105,'title':'Электрика','text':'Монтирую розетки.'}]},{'prompt_tokens':10,'completion_tokens':10},'stop'
        if number in (2,4,6):
            payload=json.loads(messages[1]['content'])
            assert [d['mcId'] for d in payload['drafts']]==([103,105] if number==2 else [105])
            return {'drafts':([{'mcId':103,'approved':True,'unsupported_claims':[],'wrong_category_claims':[]}] if number==2 else [])+[{'mcId':105,'approved':number==6,'unsupported_claims':[] if number==6 else ['лишнее обещание'],'wrong_category_claims':[]}]},{'prompt_tokens':10,'completion_tokens':10},'stop'
        payload=json.loads(messages[1]['content'])
        assert payload['invalid_mcIds']==[105]
        assert len(payload['rejected_drafts'])==1
        assert payload['rejected_drafts'][0]['review']['unsupported_claims']==['лишнее обещание']
        return {'drafts':[{'mcId':105,'title':'Электрика','text':'Монтирую розетки.'}]},{'prompt_tokens':10,'completion_tokens':10},'stop'
    monkeypatch.setattr(service,'deepseek',fake)
    r=client.post('/internal/v1/avito/drafts',headers={'X-Request-ID':'guardrail-retry-test'},json={'description':'Укладываю плитку и монтирую розетки.','mcId':101,'targetMcIds':[103,105]})
    assert r.status_code==200
    assert [d['text'] for d in r.json()['drafts']]==['Укладываю плитку.','Монтирую розетки.']
    assert len(calls)==6
    diag=client.get('/internal/v1/avito/debug/last',headers={'X-Request-ID':'guardrail-retry-test'}).json()
    assert diag['guardrailRegenerationAttempts']==2
    assert diag['guardrailRecoveredMcIds']==[105]
    assert diag['usage']['prompt_tokens']==60
def test_provided_categories_skip_evidence_selection_and_force_guard(monkeypatch):
    import app.main as service
    monkeypatch.setattr(service,'MODEL',None)
    monkeypatch.setattr(service,'evidence',lambda *args: [])
    monkeypatch.setenv('GENERATOR_PROVIDER','deepseek')
    monkeypatch.setenv('CLAIM_VERIFIER_ENABLED','false')
    calls=[]
    async def fake(messages):
        calls.append(messages)
        if 'Ты пишешь' in messages[0]['content']:
            return {'drafts':[{'mcId':103,'title':'Укладка кафеля','text':'Укладываю кафель. Работаем по договору.'}]},None,'stop'
        return {'drafts':[{'mcId':103,'approved':True,'unsupported_claims':[],'wrong_category_claims':[]}]},None,'stop'
    monkeypatch.setattr(service,'deepseek',fake)
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладываю кафель. Работаем по договору.','mcId':101,'targetMcIds':[103]})
    assert r.status_code==200 and r.json()['drafts'][0]['text']
    assert len(calls)==2
def test_classifier_targets_reach_generator_even_without_keyword_evidence(monkeypatch):
    import app.main as service
    class Classifier:
        def predict_proba(self,items):return [[.01,.95,.01,.01,.01]]
    monkeypatch.setattr(service,'MODEL',{'model':Classifier(),'class_ids':(102,103,104,105,106),'threshold':.35})
    monkeypatch.setattr(service,'evidence',lambda *args: [])
    monkeypatch.setenv('CLASSIFIER_MODE','cpu')
    monkeypatch.setenv('GENERATOR_PROVIDER','deepseek')
    monkeypatch.setenv('CLAIM_VERIFIER_ENABLED','true')
    seen=[]
    async def fake(messages):
        seen.append(messages)
        if 'Ты пишешь' in messages[0]['content']:
            assert 'source_description' in messages[1]['content']
            assert '"mcId": 103' in messages[1]['content']
            return {'drafts':[{'mcId':103,'title':'Укладка кафеля','text':'Укладываю кафель.'}]},None,'stop'
        return {'drafts':[{'mcId':103,'approved':True,'unsupported_claims':[],'wrong_category_claims':[]}]},None,'stop'
    monkeypatch.setattr(service,'deepseek',fake)
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладываю кафель.','mcId':101})
    assert r.status_code==200 and r.json()['drafts']==[{'mcId':103,'title':'Укладка кафеля','text':'Укладываю кафель.'}]
    assert len(seen)==2
def test_all_five_classifier_targets_get_independent_drafts(monkeypatch):
    monkeypatch.setenv("GENERATION_REQUEST_MODE","batch")
    import app.main as service
    class Classifier:
        def predict_proba(self,items):return [[.99]*5]
    monkeypatch.setattr(service,'MODEL',{'model':Classifier(),'class_ids':(102,103,104,105,106),'threshold':.35})
    monkeypatch.setenv('CLASSIFIER_MODE','cpu')
    monkeypatch.setenv('GENERATOR_PROVIDER','deepseek')
    monkeypatch.setenv('CLAIM_VERIFIER_ENABLED','true')
    targets=[102,103,104,105,106]
    names={102:'Штукатурка',103:'Плитка',104:'Сантехника',105:'Электрика',106:'Обои'}
    async def fake(messages):
        if 'Ты пишешь' in messages[0]['content']:
            payload=__import__('json').loads(messages[1]['content'])
            assert payload['source_description']=='Штукатурка, плитка, сантехника, электрика, обои.'
            assert [x['mcId'] for x in payload['targets']]==targets
            return {'drafts':[{'mcId':i,'title':names[i],'text':f'Выполняем работы: {names[i].lower()}.'} for i in targets]},None,'stop'
        return {'drafts':[{'mcId':i,'approved':True,'unsupported_claims':[],'wrong_category_claims':[]} for i in targets]},None,'stop'
    monkeypatch.setattr(service,'deepseek',fake)
    r=client.post('/internal/v1/avito/drafts',json={'description':'Штукатурка, плитка, сантехника, электрика, обои.','mcId':101})
    assert r.status_code==200
    assert [d['mcId'] for d in r.json()['drafts']]==targets
    assert all(d['title'] and d['text'] for d in r.json()['drafts'])
@pytest.mark.parametrize('ids',[[101],[True],['103'],[103,103],[107]])
def test_known_category_ids_are_strict(ids):
    with pytest.raises(ValueError):Input(description='Укладка плитки',mcId=101,targetMcIds=ids)
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
def test_exception_phrases_exclude_only_the_named_category():
    from app.main import explicitly_negated
    assert not evidence("Делаю всё, кроме электричества",105)
    assert explicitly_negated("Делаю всё, кроме электричества",105)
    assert explicitly_negated("Выполняю работы за исключением электрики",105)
    assert not evidence("Выполняю работы за исключением электрики",105)
    assert explicitly_negated("Всё делаю, исключая электромонтаж",105)
    assert evidence("Делаю всё, кроме сантехники, но укладываю плитку",103)
    assert not explicitly_negated("Делаю всё, кроме сантехники, но укладываю плитку",103)
    assert evidence("Делаю всё, кроме электричества, но монтирую розетки",105)
    assert not explicitly_negated("Делаю всё, кроме электричества, но монтирую розетки",105)
def test_classifier_drops_explicitly_negated_category():
    class FakeClassifier:
        def predict_proba(self,items):return [[.99,.99,.99,.99,.99]]
    assert 105 not in predict("Делаю всё, кроме электричества",101,FakeClassifier(),.3)
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
def test_generated_copy_over_backend_limits_is_dropped():
    assert valid_text('Укладываю плитку', {'title':'П'*256,'text':'Укладываю плитку'}, 103)==(None,None)
    assert valid_text('Укладываю плитку', {'title':'Плиточные работы','text':'Укладываю плитку'+'а'*10000}, 103)==(None,None)
def test_no_unsupported_separate_claim(): assert valid_text('Монтаж плитки',{'title':'Плиточные работы','text':'Можно заказать отдельно'})==(None,None)
def test_unsupported_geography_guard(): assert valid_text('Укладываем плитку',{'title':'Плиточные работы','text':'Работаем в Москве'})==(None,None)
def test_numeric_claim_must_be_in_category_evidence(): assert valid_text('Укладка плитки. Цена от 5000 рублей относится к сантехнике.',{'title':'Плиточные работы','text':'Цена от 5000 рублей'},103)==(None,None)
def test_rag_empty_store_fallback(): assert rag(103,['укладка плитки'],'some text')==[]
def test_evidence_mode_skips_classifier_and_requires_source_101(monkeypatch):
    import app.main as service
    monkeypatch.setattr(service,"MODEL",None)
    monkeypatch.setenv("CLASSIFIER_MODE","evidence")
    monkeypatch.setenv("GENERATOR_PROVIDER","disabled")
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладываю плитку и крашу стены','mcId':101})
    assert r.status_code==200
    assert [x['mcId'] for x in r.json()['drafts']]==[103,106]
    assert client.post('/internal/v1/avito/drafts',json={'description':'Укладываю плитку','mcId':102}).status_code==422
    assert client.get('/health/ready').json()['classifier']=='evidence'
def test_official_rag_example_is_available_for_related_plumbing_facts():
    assert 'organizer-104-v1' in [x['example_id'] for x in rag(104,['разводку труб и установку унитазов'],'Другой текст')]
def test_shared_source_facts_support_draft_but_other_category_price_does_not():
    source='Укладываю плитку. Опыт работы 16 лет. Работаю в Москве.'
    assert valid_text(source,{'title':'Укладка плитки','text':'Укладываю плитку. Опыт работы 16 лет. Работаю в Москве.'},103)[0]
    assert valid_text('Укладываю плитку. Сантехника: цена от 5000 рублей.',{'title':'Укладка плитки','text':'Цена от 5000 рублей'},103)==(None,None)
def test_paint_and_putty_are_category_evidence():
    text='Косметический ремонт (обои, краска, шпаклёвка под отделку).'
    found=' '.join(x['text'] for x in evidence(text,106))
    assert 'обои' in found and 'краска' in found and 'шпаклёвка' in found
def test_drywall_leveling_is_not_plaster_evidence():
    assert not evidence('Выравнивание стен и потолков гипсокартоном',102)
def test_repeated_service_phrase_is_rejected():
    assert valid_text('Делаю шпаклёвку под отделку',{'title':'Шпаклёвка','text':'Делаю шпаклёвку и шпаклёвку под отделку'},106)==(None,None)
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
    monkeypatch.setenv("GENERATION_REQUEST_MODE","batch")
    import asyncio, app.main as service
    class FakeClassifier:
        class_ids=(102,103,104,105,106)
        def predict_proba(self,items):return [[.01,.95,.01,.95,.01]]
    async def fake_deepseek(messages):
        if "Ты пишешь самостоятельные черновики" in messages[0]["content"]:
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
        if "Ты пишешь самостоятельные черновики" in messages[0]["content"]:
            return {"drafts":[{"mcId":103,"title":"Плиточные работы","text":"Укладываю плитку"}]},{"prompt_tokens":5,"completion_tokens":5},"stop"
        return {"drafts":[{"mcId":103,"approved":approved,"unsupported_claims":[],"wrong_category_claims":[]}]},{"prompt_tokens":5,"completion_tokens":5},"stop"
    monkeypatch.setattr(service,"MODEL",{"model":FakeClassifier(),"class_ids":FakeClassifier.class_ids,"input_field":"description","threshold":.35})
    monkeypatch.setattr(service,"deepseek",fake_deepseek)
    monkeypatch.setenv("GENERATOR_PROVIDER","deepseek");monkeypatch.setenv("CLASSIFIER_MODE","cpu");monkeypatch.setenv("CLAIM_VERIFIER_ENABLED","true")
    r=client.post('/internal/v1/avito/drafts',json={'description':'Укладываю плитку','mcId':101})
    assert r.status_code==200 and r.json()['drafts'][0]['text']==expected

def test_parallel_categories_accounting_and_isolation(monkeypatch):
    import asyncio,json,app.main as service
    monkeypatch.setenv("GENERATION_REQUEST_MODE","per_category")
    monkeypatch.setenv("GENERATION_CONCURRENCY","5")
    active=0;peak=0
    async def fake(messages):
        nonlocal active,peak
        data=json.loads(messages[1]["content"])
        assert len(data["targets"])==1
        mc=data["targets"][0]["mcId"]
        active+=1;peak=max(peak,active)
        await asyncio.sleep(.01)
        active-=1
        service._PROVIDER_CALLS.set(service._PROVIDER_CALLS.get()+1)
        service._REQUEST_BUDGET.set(service._REQUEST_BUDGET.get()-.01)
        if mc==104:return {"drafts":[{"mcId":104,"title":"Invalid","text":"Invalid","text_alt":None}]},{"prompt_tokens":10},"stop"
        return {"drafts":[{"mcId":mc,"title":"Service","text":"Supported text"}]},{"prompt_tokens":10},"stop"
    monkeypatch.setattr(service,"deepseek",fake)
    async def run():
        bt=service._REQUEST_BUDGET.set(.5);ct=service._PROVIDER_CALLS.set(0)
        try:
            result,usage,_=await service.deepseek_categories([{"role":"system","content":"generate"},{"role":"user","content":json.dumps({"source_description":"source","targets":[{"mcId":i} for i in [102,103,104,105,106]]})}])
            assert peak==5
            assert [d["mcId"] for d in result["drafts"]]==[102,103,104,105,106]
            assert result["drafts"][2]["text"] is None
            assert result["drafts"][0]["text"]
            assert service._PROVIDER_CALLS.get()==5
            assert service._REQUEST_BUDGET.get()==pytest.approx(.45)
            assert usage["prompt_tokens"]==50
        finally:
            service._REQUEST_BUDGET.reset(bt);service._PROVIDER_CALLS.reset(ct)
    asyncio.run(run())

@pytest.mark.parametrize("source,mc,title,text",[
 ("Подготовка стен, шпаклевка и покраска.",102,"Штукатурные работы","Выполняю штукатурные работы."),
 ("Штукатурка стен. Выезд на замер.",102,"Штукатурные работы","Выезд на замер."),
 ("Штукатурка, шпаклевка, покраска стен.",106,"Покраска стен","Штукатурю, шпаклюю и крашу стены."),
])
def test_fact_scope_regressions(source,mc,title,text):
    assert valid_text(source,{"title":title,"text":text},mc,semantic=True)==(None,None)

@pytest.mark.parametrize("source,mc,title,text",[
 ("Выполняю штукатурку стен.",102,"Штукатурка стен","Выполняю штукатурку стен."),
 ("В бригаде есть маляр.",106,"Малярные работы","В бригаде есть маляр."),
 ("Сантехника.",104,"Сантехнические работы","Выполняю сантехнические работы."),
])
def test_short_factual_descriptions_remain_valid(source,mc,title,text):
    assert valid_text(source,{"title":title,"text":text},mc,semantic=True)==(title,text)
