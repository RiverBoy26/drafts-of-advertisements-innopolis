import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowDownWideNarrow, ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronRight,
  CircleHelp, Clipboard, Copy, FileCheck2, FilePenLine, FilePlus2, FileText,
  Home, Layers3, LogOut, Menu, Pencil, Plus, Search, ShieldCheck, Sparkles,
  Trash2, WandSparkles, X, AlertCircle, LoaderCircle, Eye, EyeOff, PanelLeftClose,
} from 'lucide-react';
import { analyzeText, exportDraft, generateDrafts, isDemo, searchCategories, updateDraft } from './api';
import { exampleText } from './mockApi';

const STORAGE = 'draftly-v1';
const readSaved = () => {
  try { return JSON.parse(localStorage.getItem(STORAGE)) || {}; } catch { return {}; }
};
const initial = readSaved();
const emptyMessage = '—';

function Logo({ small = false }) {
  return <span className={`brand ${small ? 'brand-small' : ''}`}>
    <img src="/logo_draftly.png" alt="Draftly" />
  </span>;
}

function Button({ children, variant = 'secondary', className = '', ...props }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>;
}

function Field({ label, hint, error, ...props }) {
  const id = props.id || props.name;
  return <label className="field" htmlFor={id}>
    <span>{label}</span>
    <input id={id} {...props} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} />
    {hint && <small>{hint}</small>}
    {error && <small className="field-error" id={`${id}-error`}>{error}</small>}
  </label>;
}

function AuthPage({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = event => {
    event.preventDefault(); setError('');
    if (!name.trim() && mode === 'register') return setError('Укажите ваше имя.');
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError('Проверьте формат электронной почты.');
    if (password.length < 6) return setError('Пароль должен содержать не менее 6 символов.');
    if (mode === 'register' && password !== repeat) return setError('Пароли не совпадают.');
    setBusy(true);
    window.setTimeout(() => {
      onLogin({ name: mode === 'register' ? name.trim() : email.split('@')[0], email });
      setBusy(false);
    }, 250);
  };
  return <main className="auth-page">
    <section className="auth-panel" aria-labelledby="auth-title">
      <Logo />
      <div className="auth-heading">
        <h1 id="auth-title">{mode === 'login' ? 'С возвращением' : 'Создать аккаунт'}</h1>
        <p>{mode === 'login' ? 'Войдите, чтобы продолжить работу с объявлениями' : 'Начните создавать объявления быстрее с Draftly'}</p>
      </div>
      <form onSubmit={submit} noValidate>
        {mode === 'register' && <Field label="Имя" id="auth-name" autoComplete="name" value={name} onChange={e => setName(e.target.value)} placeholder="Как к вам обращаться?" required />}
        <Field label="Электронная почта" id="auth-email" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" required />
        <div className="password-field">
          <Field label="Пароль" id="auth-password" type={showPassword ? 'text' : 'password'} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} placeholder="Не менее 6 символов" required />
          <button type="button" className="password-toggle" aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'} onClick={() => setShowPassword(v => !v)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
        </div>
        {mode === 'register' && <Field label="Повторите пароль" id="auth-repeat" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={repeat} onChange={e => setRepeat(e.target.value)} placeholder="Введите пароль ещё раз" required />}
        {error && <p className="form-error" role="alert"><AlertCircle size={16} />{error}</p>}
        <Button variant="primary" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : null}{mode === 'login' ? 'Войти' : 'Создать аккаунт'}<ArrowRight size={16} /></Button>
      </form>
      <p className="auth-switch">{mode === 'login' ? 'Ещё нет аккаунта?' : 'Уже есть аккаунт?'} <button type="button" className="link-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>{mode === 'login' ? 'Зарегистрироваться' : 'Войти'}</button></p>
      <div className="auth-note"><ShieldCheck size={15} /> Демо-режим: данные остаются в этом браузере.</div>
    </section>
  </main>;
}

const navigation = [
  { id: 'overview', label: 'Обзор', Icon: Home },
  { id: 'analysis', label: 'Новый анализ', Icon: Sparkles },
  { id: 'drafts', label: 'Черновики', Icon: FileText },
  { id: 'ads', label: 'Мои объявления', Icon: FileCheck2 },
];

function AppHeader({ user, activePage, counts, onNavigate, onLogout }) {
  const [drawer, setDrawer] = useState(false);
  const [profile, setProfile] = useState(false);
  const title = navigation.find(item => item.id === activePage)?.label || 'Новое объявление';
  useEffect(() => {
    const close = event => { if (event.key === 'Escape') { setDrawer(false); setProfile(false); } };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);
  const go = page => { onNavigate(page); setDrawer(false); };
  return <>
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-button menu-trigger" aria-label="Открыть меню" onClick={() => setDrawer(true)}><Menu size={20} /></button>
        <Logo small /><span className="topbar-divider" /><span className="current-page">{title}</span>
      </div>
      <div className="profile-wrap">
        <button className="profile-trigger" aria-expanded={profile} onClick={() => setProfile(v => !v)}>
          <span className="avatar">{(user.name || 'П').slice(0, 1).toUpperCase()}</span><span className="profile-name">{user.name}</span><ChevronRight className={profile ? 'rotate-down' : 'rotate-right'} size={15} />
        </button>
        {profile && <div className="profile-menu"><strong>{user.name}</strong><small>{user.email}</small><button onClick={() => { setProfile(false); onLogout(); }}><LogOut size={16} /> Выйти</button></div>}
      </div>
    </header>
    {drawer && <div className="drawer-layer">
      <button className="drawer-backdrop" aria-label="Закрыть меню" onClick={() => setDrawer(false)} />
      <aside className="navigation-drawer" aria-label="Основная навигация">
        <div className="drawer-header"><Logo small /><button className="icon-button" aria-label="Закрыть меню" onClick={() => setDrawer(false)}><PanelLeftClose size={19} /></button></div>
        <nav>{navigation.map(({ id, label, Icon }) => <button key={id} className={`nav-item ${activePage === id ? 'active' : ''}`} onClick={() => go(id)}><Icon size={18} /><span>{label}</span>{id === 'drafts' && <small>{counts.drafts}</small>}{id === 'ads' && <small>{counts.ads}</small>}</button>)}</nav>
        <div className="drawer-footer"><CircleHelp size={16} /><span>Draftly помогает разложить описание на отдельные объявления.</span></div>
      </aside>
    </div>}
  </>;
}

function PageHeading({ title, subtitle, action }) {
  return <div className="page-heading"><div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{action}</div>;
}

function OverviewPage({ user, drafts, ads, totalPrepared, navigate }) {
  const stats = [
    { label: 'Черновики', value: drafts.length, Icon: FileText },
    { label: 'Мои объявления', value: ads.length, Icon: FileCheck2 },
    { label: 'Всего подготовлено', value: totalPrepared, Icon: Layers3 },
  ];
  return <>
    <PageHeading title="Обзор" subtitle="Всё необходимое для создания и управления объявлениями" />
    <section className="welcome-panel">
      <div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h2>Превратите свои услуги в готовые объявления</h2><p>Расскажите, чем вы занимаетесь. Draftly найдёт отдельные направления и подготовит тексты для публикации.</p><Button variant="primary" onClick={() => navigate('analysis')}><Sparkles size={17} /> Начать анализ <ArrowRight size={16} /></Button></div>
      <div className="welcome-note"><span><FileCheck2 size={20} /></span><div><strong>Один текст — несколько направлений</strong><small>Проверьте каждое перед созданием объявления</small></div></div>
    </section>
    <section className="stats-row" aria-label="Статистика">
      {stats.map(({ label, value, Icon }) => <div className="stat-item" key={label}><span className="stat-icon"><Icon size={18} /></span><div><strong>{value}</strong><small>{label}</small></div></div>)}
    </section>
    <section className="quick-section"><div className="section-heading"><div><h2>Быстрый доступ</h2><p>Продолжите работу или начните с нового описания</p></div></div>
      <div className="quick-links">
        <button onClick={() => navigate('analysis')}><span><Sparkles size={18} /></span><div><strong>Новый анализ</strong><small>Найдите услуги в исходном тексте</small></div><ChevronRight size={17} /></button>
        <button onClick={() => navigate('drafts')}><span><FileText size={18} /></span><div><strong>Черновики</strong><small>{drafts.length ? `${drafts.length} подготовленных объявлений` : 'Проверьте созданные варианты'}</small></div><ChevronRight size={17} /></button>
        <button onClick={() => navigate('ads')}><span><FileCheck2 size={18} /></span><div><strong>Мои объявления</strong><small>{ads.length ? `${ads.length} одобренных объявлений` : 'Сохраните готовые к публикации'}</small></div><ChevronRight size={17} /></button>
      </div>
    </section>
    {drafts.length > 0 && <section className="recent-section"><div className="section-heading"><div><h2>Недавние черновики</h2></div><button className="link-button" onClick={() => navigate('drafts')}>Все черновики <ArrowRight size={15} /></button></div><div className="recent-list">{drafts.slice(0, 3).map(d => <button key={d.id} onClick={() => navigate('drafts')}><FileText size={17} /><span><strong>{d.title}</strong><small>{d.microcategory || d.category || 'Категория не указана'}</small></span><ChevronRight size={16} /></button>)}</div></section>}
  </>;
}

function AnalysisPage({ text, setText, sourceText, services, setServices, onAnalyze, onGenerate, onGenerateOne, onNavigate, busy, error, clearError, analysisReady, generatedCount }) {
  const selectedCount = services.filter(service => service.selected).length;
  const [expanded, setExpanded] = useState(false);
  return <>
    <PageHeading title="Новый анализ" subtitle="Вставьте описание — Draftly выделит отдельные направления и подготовит объявления." action={generatedCount ? <Button onClick={() => onNavigate('generated')}><FileText size={15} /> Подготовленные объявления ({generatedCount})</Button> : null} />
    <section className="source-panel">
      <div className="section-heading"><div><h2>Опишите, чем вы занимаетесь</h2><p>Опишите товары, услуги или свою деятельность простыми словами.</p></div></div>
      <textarea className="source-input" value={text} onChange={e => setText(e.target.value)} maxLength={10000} placeholder="Например: Выполняю ремонт квартир под ключ. Укладываю плитку, клею обои и устанавливаю двери…" aria-label="Исходное описание" />
      <div className="source-tools"><span>{text.length.toLocaleString('ru-RU')} / 10 000 символов</span><div>{text && <button className="link-button muted-link" onClick={() => setText('')}><X size={14} /> Очистить</button>}<button className="link-button" onClick={() => setText(exampleText)}><WandSparkles size={15} /> Вставить пример</button></div></div>
      {error && <div className="inline-alert" role="alert"><AlertCircle size={16} /><span>{error}</span><button aria-label="Закрыть сообщение" onClick={clearError}><X size={15} /></button></div>}
      <div className="source-submit"><Button variant="primary" onClick={onAnalyze} disabled={busy === 'analyze' || text.trim().length < 12}>{busy === 'analyze' ? <LoaderCircle size={17} className="spin" /> : <Search size={17} />}{busy === 'analyze' ? 'Анализируем описание…' : 'Найти услуги'}<ArrowRight size={16} /></Button><small>Текст отправится на анализ и останется доступен для проверки.</small></div>
    </section>
    {analysisReady && <section className="results-section">
      <div className="source-summary"><div><strong>Исходное описание</strong><span>{sourceText.length.toLocaleString('ru-RU')} символов</span></div><p className={!expanded ? 'clamp-text' : ''}>{sourceText}</p>{sourceText.length > 180 && <button className="link-button" onClick={() => setExpanded(v => !v)}>{expanded ? 'Свернуть' : 'Развернуть полностью'}</button>}</div>
      <div className="section-heading results-heading"><div><h2>Результаты анализа <span className="count-label">{services.length}</span></h2><p>Проверьте найденные направления перед созданием объявлений.</p></div></div>
      {services.length === 0 ? <EmptyState title="Услуги не найдены" description="Попробуйте добавить больше подробностей и запустить анализ ещё раз." action={<Button variant="secondary" onClick={() => setText(exampleText)}>Вставить пример</Button>} /> : <>
        {isDemo && <p className="demo-caption"><ShieldCheck size={14} /> Демонстрационный анализ по ключевым словам</p>}
        <div className="service-list">{services.map((service, index) => <ServiceResult key={service.id} service={service} index={index} busy={busy === `generate-${service.id}`} onChange={next => setServices(prev => prev.map(item => item.id === service.id ? next : item))} onDelete={() => onGenerateOne(service, 'delete')} onGenerate={() => onGenerateOne(service, 'generate')} />)}</div>
        <div className="bulk-action"><div><strong>{selectedCount} из {services.length} выбрано</strong><small>Можно сформировать отдельное объявление у каждой услуги.</small></div><Button variant="primary" disabled={!selectedCount || busy.startsWith('generate')} onClick={onGenerate}>{busy === 'generate' ? <LoaderCircle size={17} className="spin" /> : <Sparkles size={17} />}{busy === 'generate' ? 'Формируем объявления…' : `Сформировать объявления (${selectedCount})`}</Button></div>
      </>}
    </section>}
  </>;
}

function ServiceResult({ service, index, onChange, onDelete, onGenerate, busy }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(service.service || '');
  const [microcategory, setMicrocategory] = useState(service.microcategory || '');
  const [category, setCategory] = useState(service.category || '');
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [editError, setEditError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  useEffect(() => {
    if (!editing || microcategory.trim().length < 2) { setCategoryOptions([]); return undefined; }
    let active = true;
    const timer = window.setTimeout(() => { searchCategories(microcategory).then(items => { if (active) setCategoryOptions(items); }).catch(() => { if (active) setCategoryOptions([]); }); }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [editing, microcategory]);
  const save = () => {
    const changedCategory = microcategory.trim() !== (service.microcategory || '');
    const match = categoryOptions.find(item => item.name.toLowerCase() === microcategory.trim().toLowerCase());
    if (changedCategory && !match && !isDemo) { setEditError('Выберите подкатегорию из справочника.'); return; }
    onChange({ ...service, service: name.trim(), title: name.trim() === service.service ? service.title : name.trim(), category: match?.path?.[0] || category.trim(), microcategory: match?.name || microcategory.trim(), categoryId: match?.parentId || service.categoryId, microcategoryId: match?.id || service.microcategoryId, classificationDirty: service.classificationDirty || changedCategory });
    setEditError(''); setEditing(false);
  };
  return <article className="service-result">
    <div className="service-result-main">
      <label className="selection-control"><input type="checkbox" checked={service.selected !== false} onChange={e => onChange({ ...service, selected: e.target.checked })} /><span className="custom-check"><Check size={13} /></span><span className="sr-only">Выбрать {service.service}</span></label>
      <span className="result-number">{String(index + 1).padStart(2, '0')}</span>
      <div className="result-copy"><div className="result-title"><h3>{service.service || 'Направление без названия'}</h3>{service.confidence && <span className={`confidence confidence-${service.confidence}`}>{service.confidence === 'low' ? 'Низкая уверенность' : service.confidence === 'medium' ? 'Проверьте категорию' : 'Категория найдена'}</span>}</div>
        <div className="category-line"><span>{service.category || 'Категория не указана'}</span><ChevronRight size={13} /><strong>{service.microcategory || 'Подкатегория не указана'}</strong></div>
        {service.sourceFragment && <p className="source-fragment">«{service.sourceFragment}»</p>}
      </div>
      <div className="result-actions"><button className="icon-button" aria-label="Изменить направление" onClick={() => { setName(service.service || ''); setCategory(service.category || ''); setMicrocategory(service.microcategory || ''); setEditing(v => !v); }}><Pencil size={16} /></button><button className="icon-button danger-icon" aria-label="Удалить направление" onClick={() => setDeleteConfirm(true)}><Trash2 size={16} /></button></div>
    </div>
    {editing && <div className="service-edit"><Field label="Название" value={name} onChange={e => setName(e.target.value)} /><Field label="Категория" value={category} onChange={e => setCategory(e.target.value)} /><label className="field"><span>Подкатегория</span><input list={`categories-${service.id}`} value={microcategory} onChange={e => { setMicrocategory(e.target.value); setEditError(''); }} /><datalist id={`categories-${service.id}`}>{categoryOptions.map(item => <option key={item.id} value={item.name}>{item.path?.join(' → ')}</option>)}</datalist></label>{editError && <p className="form-error" role="alert">{editError}</p>}<div className="edit-actions"><Button onClick={() => { setEditing(false); setEditError(''); }}>Отмена</Button><Button variant="primary" disabled={!name.trim()} onClick={save}><Check size={15} /> Применить</Button></div></div>}
    <div className="service-bottom"><span>{service.sourceFragment ? 'Фрагмент исходного описания показан выше' : 'Проверьте название и категорию перед созданием'}</span><Button variant="primary" className="small-button" disabled={!service.selected || busy} onClick={onGenerate}>{busy ? <LoaderCircle size={15} className="spin" /> : <FilePlus2 size={15} />}{busy ? 'Создаём…' : 'Сформировать объявление'}</Button></div>
    {deleteConfirm && <ConfirmModal title="Удалить направление?" description={`«${service.service}» исчезнет из результатов этого анализа.`} confirmLabel="Удалить направление" onCancel={() => setDeleteConfirm(false)} onConfirm={() => { setDeleteConfirm(false); onDelete(); }} />}
  </article>;
}

function EmptyState({ title, description, action }) {
  return <div className="empty-state"><span><FileText size={21} /></span><h3>{title}</h3><p>{description}</p>{action}</div>;
}

function AdCard({ item, index, section, onEdit, onCopy, onRemove, onApprove }) {
  return <article className="ad-card"><div className="ad-card-top"><span className="result-number">{String(index + 1).padStart(2, '0')}</span><span className={`status-pill ${section === 'ads' ? 'status-ready' : ''}`}>{section === 'ads' ? 'Готово к публикации' : section === 'generated' ? 'Подготовлено' : 'Черновик'}</span><time>{item.updatedAt || item.createdAt ? new Date(item.updatedAt || item.createdAt).toLocaleDateString('ru-RU') : 'Сегодня'}</time></div>
    <h3>{item.title}</h3><p className="ad-category">{item.category || 'Категория не указана'}{item.microcategory ? ` · ${item.microcategory}` : ''}</p><p className="ad-description">{item.description || 'Описание пока не добавлено.'}</p>
    <div className="ad-actions"><Button variant="secondary" onClick={() => onCopy(item)}><Copy size={15} /> Скопировать</Button><Button variant="secondary" onClick={() => onEdit(item)}><Pencil size={15} /> Редактировать</Button>{section === 'drafts' ? <Button variant="soft" onClick={() => onApprove(item)}><CheckCircle2 size={15} /> В мои объявления</Button> : section === 'generated' ? <Button variant="soft" onClick={() => onApprove(item)}><FileText size={15} /> Сохранить в черновики</Button> : <Button variant="soft" onClick={() => onApprove(item)}><ArrowLeft size={15} /> В черновики</Button>}<button className="icon-button danger-icon" aria-label="Удалить объявление" onClick={() => onRemove(item)}><Trash2 size={16} /></button></div>
  </article>;
}

function CollectionPage({ section, items, onNavigate, onEdit, onCopy, onRemove, onApprove, error, clearError }) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('newest');
  const isAds = section === 'ads';
  const sorted = useMemo(() => items.filter(item => `${item.title} ${item.description} ${item.microcategory || ''} ${item.category || ''}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => {
    const aDate = new Date(a.updatedAt || a.createdAt || 0).getTime(); const bDate = new Date(b.updatedAt || b.createdAt || 0).getTime();
    return sort === 'newest' ? bDate - aDate : aDate - bDate;
  }), [items, query, sort]);
  return <>
    <PageHeading title={isAds ? 'Мои объявления' : 'Черновики'} subtitle={isAds ? 'Сохранённые объявления, которые вы готовы использовать для публикации.' : 'Подготовленные объявления. Проверьте текст, внесите изменения и скопируйте.'} action={<Button variant="primary" onClick={() => onNavigate('analysis')}><Plus size={16} /> Создать новое</Button>} />
    {error && <div className="inline-alert" role="alert"><AlertCircle size={16} /><span>{error}</span><button aria-label="Закрыть сообщение" onClick={clearError}><X size={15} /></button></div>}
    <div className="collection-toolbar"><div className="collection-count"><strong>{items.length}</strong><span>{isAds ? 'сохранено' : 'всего черновиков'}</span></div><label className="search-control"><Search size={17} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Поиск по названию и описанию" aria-label="Поиск объявлений" />{query && <button aria-label="Очистить поиск" onClick={() => setQuery('')}><X size={14} /></button>}</label><label className="sort-control"><ArrowDownWideNarrow size={16} /><select value={sort} onChange={e => setSort(e.target.value)} aria-label="Сортировка по дате"><option value="newest">Сначала новые</option><option value="oldest">Сначала старые</option></select></label></div>
    {sorted.length ? <div className="ad-list">{sorted.map((item, index) => <AdCard key={item.id} item={item} index={index} section={section} onEdit={onEdit} onCopy={onCopy} onRemove={onRemove} onApprove={onApprove} />)}</div> : <EmptyState title={items.length ? 'Ничего не найдено' : isAds ? 'Здесь появятся ваши объявления' : 'Пока нет черновиков'} description={items.length ? 'Измените запрос поиска и попробуйте снова.' : isAds ? 'Переносите сюда понравившиеся варианты из черновиков, чтобы быстро находить их и копировать.' : 'Проведите анализ исходного описания и сформируйте первое объявление.'} action={<Button variant={items.length ? 'secondary' : 'primary'} onClick={() => items.length ? setQuery('') : onNavigate(isAds ? 'drafts' : 'analysis')}>{items.length ? 'Сбросить поиск' : isAds ? 'Перейти к черновикам' : 'Начать анализ'}</Button>} />}
  </>;
}

function EditModal({ item, busy, onClose, onSave }) {
  const [edited, setEdited] = useState({ ...item });
  const [error, setError] = useState('');
  useEffect(() => { const close = e => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close); }, [onClose]);
  return <div className="modal-layer" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="edit-title"><div className="modal-head"><div><h2 id="edit-title">Редактировать объявление</h2><p>Изменения сохранятся в текущем списке.</p></div><button className="icon-button" aria-label="Закрыть" onClick={onClose}><X size={18} /></button></div><div className="modal-body"><Field label="Заголовок" value={edited.title || ''} onChange={e => setEdited(prev => ({ ...prev, title: e.target.value }))} maxLength={100} /><label className="field"><span>Описание</span><textarea rows={8} value={edited.description || ''} onChange={e => setEdited(prev => ({ ...prev, description: e.target.value }))} /></label>{error && <p className="form-error" role="alert">{error}</p>}</div><div className="modal-actions"><Button onClick={onClose}>Отмена</Button><Button variant="primary" disabled={busy || !edited.title.trim() || !edited.description.trim()} onClick={async () => { try { await onSave(edited); } catch (err) { setError(err.message || 'Не удалось сохранить изменения.'); } }}><Check size={16} /> {busy ? 'Сохраняем…' : 'Сохранить'}</Button></div></section></div>;
}

function ConfirmModal({ title, description, confirmLabel, onCancel, onConfirm, danger = true }) {
  useEffect(() => { const close = e => { if (e.key === 'Escape') onCancel(); }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close); }, [onCancel]);
  return <div className="modal-layer nested-modal" onMouseDown={e => { if (e.target === e.currentTarget) onCancel(); }}><section className="modal confirm-modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title"><div className="modal-head"><div><h2 id="confirm-title">{title}</h2><p>{description}</p></div><button className="icon-button" aria-label="Закрыть" onClick={onCancel}><X size={18} /></button></div><div className="modal-actions"><Button onClick={onCancel}>Отмена</Button><Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>{confirmLabel}</Button></div></section></div>;
}

function App() {
  const [user, setUser] = useState(initial.user || null);
  const [page, setPage] = useState('overview');
  const [text, setText] = useState(initial.text || '');
  const [analysisSource, setAnalysisSource] = useState(initial.analysisSource || initial.text || '');
  const [analysisId, setAnalysisId] = useState(initial.analysisId || null);
  const [services, setServices] = useState(initial.services || []);
  const [analysisReady, setAnalysisReady] = useState(initial.analysisReady ?? Boolean((initial.services || []).length));
  const [drafts, setDrafts] = useState(initial.drafts || []);
  const [ads, setAds] = useState(initial.ads || []);
  const [results, setResults] = useState(initial.results || []);
  const [totalPrepared, setTotalPrepared] = useState(initial.totalPrepared ?? ((initial.drafts || []).length + (initial.ads || []).length + (initial.results || []).length));
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [editItem, setEditItem] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [generatedItem, setGeneratedItem] = useState(null);

  useEffect(() => { localStorage.setItem(STORAGE, JSON.stringify({ user, text, analysisSource, analysisId, services, analysisReady, drafts, ads, results, totalPrepared })); }, [user, text, analysisSource, analysisId, services, analysisReady, drafts, ads, results, totalPrepared]);
  useEffect(() => { if (!toast) return undefined; const timer = window.setTimeout(() => setToast(''), 3000); return () => window.clearTimeout(timer); }, [toast]);
  const navigate = next => { setPage(next); setError(''); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const notify = message => setToast(message);
  const analyze = async () => {
    if (text.trim().length < 12) { setError('Добавьте описание не короче 12 символов.'); return; }
    setBusy('analyze'); setError('');
    try { const submittedText = text; const response = await analyzeText(submittedText); setAnalysisSource(submittedText); setAnalysisId(response.analysisId); setServices(response.services); setAnalysisReady(true); setResults([]); notify(`Анализ завершён. Найдено направлений: ${response.services.length}`); }
    catch (err) { setError(err.message || 'Не удалось выполнить анализ. Попробуйте ещё раз.'); }
    finally { setBusy(''); }
  };
  const generateSelected = async chosen => {
    if (!chosen.length) { setError('Выберите хотя бы одно направление.'); return; }
    setBusy('generate'); setError('');
    try { const created = await generateDrafts(analysisId, chosen); setResults(prev => [...created, ...prev]); setTotalPrepared(value => value + created.length); setGeneratedItem(created.length === 1 ? created[0] : null); if (created.length > 1) setPage('generated'); notify(created.length === 1 ? 'Объявление сформировано' : `Сформировано объявлений: ${created.length}`); }
    catch (err) { setError(err.message || 'Не удалось сформировать объявления.'); }
    finally { setBusy(''); }
  };
  const generateOne = async service => {
    if (!service.selected) setServices(prev => prev.map(item => item.id === service.id ? { ...item, selected: true } : item));
    setBusy(`generate-${service.id}`); setError('');
    try { const created = await generateDrafts(analysisId, [{ ...service, selected: true }]); setResults(prev => [...created, ...prev]); setTotalPrepared(value => value + created.length); setGeneratedItem(created[0] || null); notify('Объявление сформировано'); }
    catch (err) { setError(err.message || 'Не удалось сформировать объявление.'); }
    finally { setBusy(''); }
  };
  const saveResult = item => { setDrafts(prev => prev.some(d => d.id === item.id) ? prev : [item, ...prev]); setResults(prev => prev.filter(d => d.id !== item.id)); notify('Объявление добавлено в черновики'); setGeneratedItem(null); };
  const saveAllResults = () => { const existing = new Set(drafts.map(d => d.id)); const fresh = results.filter(d => !existing.has(d.id)); setDrafts(prev => [...fresh, ...prev]); setResults([]); navigate('drafts'); notify(fresh.length ? `Сохранено черновиков: ${fresh.length}` : 'Эти объявления уже сохранены'); };
  const copyItem = async item => { try { const content = await exportDraft(item); await navigator.clipboard.writeText(content); notify('Объявление скопировано'); } catch { notify('Не удалось скопировать. Разрешите доступ к буферу обмена.'); } };
  const saveEdit = async item => {
    setBusy('edit'); setError('');
    try {
      const saved = await updateDraft(item);
      setDrafts(prev => prev.map(d => d.id === saved.id ? saved : d)); setAds(prev => prev.map(d => d.id === saved.id ? saved : d)); setResults(prev => prev.map(d => d.id === saved.id ? saved : d)); setGeneratedItem(current => current?.id === saved.id ? saved : current); setEditItem(null); notify('Изменения сохранены');
    } catch (err) { setBusy(''); throw err; }
    setBusy('');
  };
  const removeItem = (item, from) => setConfirm({ title: 'Удалить объявление?', description: `«${item.title}» будет удалено ${from === 'ads' ? 'из ваших объявлений' : 'из черновиков'}.`, confirmLabel: 'Удалить', onConfirm: () => { if (from === 'ads') setAds(prev => prev.filter(d => d.id !== item.id)); else setDrafts(prev => prev.filter(d => d.id !== item.id)); setConfirm(null); notify('Объявление удалено'); } });
  const moveItem = (item, from) => {
    if (from === 'drafts') { setDrafts(prev => prev.filter(d => d.id !== item.id)); setAds(prev => prev.some(d => d.id === item.id) ? prev : [{ ...item, status: 'Готово', updatedAt: new Date().toISOString() }, ...prev]); notify('Объявление перенесено в мои объявления'); }
    else { setAds(prev => prev.filter(d => d.id !== item.id)); setDrafts(prev => prev.some(d => d.id === item.id) ? prev : [{ ...item, status: 'Черновик', updatedAt: new Date().toISOString() }, ...prev]); notify('Объявление возвращено в черновики'); }
  };
  if (!user) return <AuthPage onLogin={setUser} />;
  return <div className="app-shell">
    <AppHeader user={user} activePage={page} counts={{ drafts: drafts.length, ads: ads.length }} onNavigate={navigate} onLogout={() => { setUser(null); navigate('overview'); }} />
    <main className="main-content">
      {error && page !== 'analysis' && page !== 'drafts' && page !== 'ads' && <div className="inline-alert" role="alert"><AlertCircle size={16} /><span>{error}</span><button aria-label="Закрыть сообщение" onClick={() => setError('')}><X size={15} /></button></div>}
      {page === 'overview' && <OverviewPage user={user} drafts={drafts} ads={ads} totalPrepared={totalPrepared} navigate={navigate} />}
      {page === 'analysis' && <AnalysisPage text={text} setText={setText} sourceText={analysisSource} services={services} setServices={setServices} onAnalyze={analyze} onGenerate={() => generateSelected(services.filter(service => service.selected))} onGenerateOne={(service, action) => action === 'delete' ? setServices(prev => prev.filter(item => item.id !== service.id)) : generateOne(service)} onNavigate={navigate} busy={busy} error={error} clearError={() => setError('')} analysisReady={analysisReady} generatedCount={results.length} />}
      {(page === 'drafts' || page === 'ads') && <CollectionPage section={page} items={page === 'drafts' ? drafts : ads} onNavigate={navigate} onEdit={setEditItem} onCopy={copyItem} onRemove={item => removeItem(item, page)} onApprove={item => moveItem(item, page)} error={error} clearError={() => setError('')} />}
      {page === 'generated' && <>
        <PageHeading title="Объявления готовы" subtitle="Проверьте подготовленные тексты и выберите, что сохранить." action={<Button onClick={() => navigate('analysis')}><ArrowLeft size={15} /> К результатам анализа</Button>} />
        {results.length ? <><div className="ad-list">{results.map((item, index) => <AdCard key={`${item.id}-${index}`} item={item} index={index} section="generated" onEdit={setEditItem} onCopy={copyItem} onRemove={ad => setResults(prev => prev.filter(d => d.id !== ad.id))} onApprove={saveResult} />)}</div><div className="bulk-action"><div><strong>{results.length} подготовлено</strong><small>Сохраните понравившиеся варианты в черновики.</small></div><Button variant="primary" onClick={saveAllResults}><Check size={16} /> Сохранить все черновики</Button></div></> : <EmptyState title="Нет новых объявлений" description="Сформируйте объявление для одной или нескольких услуг." action={<Button variant="primary" onClick={() => navigate('analysis')}>Вернуться к результатам</Button>} />}
      </>}
    </main>
    {toast && <div className="toast" role="status"><CheckCircle2 size={17} />{toast}</div>}
    {editItem && <EditModal item={editItem} busy={busy === 'edit'} onClose={() => setEditItem(null)} onSave={saveEdit} />}
    {confirm && <ConfirmModal {...confirm} onCancel={() => setConfirm(null)} />}
    {generatedItem && <GeneratedModal item={generatedItem} onClose={() => setGeneratedItem(null)} onEdit={() => { setEditItem(generatedItem); setGeneratedItem(null); }} onCopy={() => copyItem(generatedItem)} onSave={() => saveResult(generatedItem)} onReturn={() => { setGeneratedItem(null); navigate('analysis'); }} />}
  </div>;
}

function GeneratedModal({ item, onClose, onEdit, onCopy, onSave, onReturn }) {
  return <div className="modal-layer" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><section className="modal generated-modal" role="dialog" aria-modal="true" aria-labelledby="generated-title"><div className="modal-head"><div><span className="success-mark"><Check size={17} /></span><h2 id="generated-title">Ваше объявление готово</h2><p>Публикация на площадке выполняется отдельно.</p></div><button className="icon-button" aria-label="Закрыть" onClick={onClose}><X size={18} /></button></div><div className="modal-body generated-body"><div><small>ЗАГОЛОВОК</small><strong>{item.title}</strong></div><div><small>КАТЕГОРИЯ</small><strong>{item.category || emptyMessage}{item.microcategory ? ` · ${item.microcategory}` : ''}</strong></div><div><small>ОПИСАНИЕ</small><p>{item.description}</p></div><button className="link-button" onClick={onEdit}><Pencil size={14} /> Редактировать текст</button></div><div className="modal-actions generated-actions"><Button onClick={onReturn}>К результатам анализа</Button><Button onClick={onCopy}><Copy size={15} /> Скопировать</Button><Button variant="primary" onClick={onSave}><FileText size={15} /> Сохранить в черновики</Button></div></section></div>;
}

export default App;
