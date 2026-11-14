import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronDown, ChevronRight,
  CircleHelp, Copy, FileCheck2, FilePenLine, FileText, Grid3X3, House,
  LogOut, Menu, Paintbrush, PaintRoller, Pencil, Plus, Search, ShieldCheck,
  Sparkles, Trash2, Wrench, X, AlertCircle, LoaderCircle, Eye, EyeOff,
  PanelLeftClose, UserRound, Zap, SlidersHorizontal, Clock3,
} from 'lucide-react';

// Справочник микрокатегорий
const MICROCATEGORIES = [
  { mcId: 101, name: 'Ремонт под ключ' },
  { mcId: 102, name: 'Штукатурные работы' },
  { mcId: 103, name: 'Плиточные работы' },
  { mcId: 104, name: 'Сантехника' },
  { mcId: 105, name: 'Электрика' },
  { mcId: 106, name: 'Поклейка обоев и малярные работы' },
];

// Временные данные до подключения backend
const MOCK_RESULTS = {
  101: [104, 105],
  102: [106],
  103: [104],
  104: [101, 105],
  105: [104],
  106: [102],
};

function getMockResults(sourceMcId) {
  return {
    drafts: (MOCK_RESULTS[sourceMcId] || [])
      .filter(targetMcId => targetMcId !== sourceMcId)
      .map(targetMcId => ({
        mcId: targetMcId,
        title: null,
        text: null,
      })),
    demo: true,
    evidence: {},
  };
}

const STORAGE = 'draftly-case-2026-v1';
const LEGACY_STORAGE = 'draftly-v1';

const safeRead = key => {
  try {
    return JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return {};
  }
};

const initial = safeRead(STORAGE);
const previous = safeRead(LEGACY_STORAGE);

const categoryFor = mcId =>
  MICROCATEGORIES.find(c => c.mcId === Number(mcId));

const icons = {
  101: House,
  102: PaintRoller,
  103: Grid3X3,
  104: Wrench,
  105: Zap,
  106: Paintbrush,
};

function Logo({ small = false }) {
  return (
    <span className={`brand ${small ? 'brand-small' : ''}`}>
      <img src="/logo_draftly.png" alt="Draftly" />
    </span>
  );
}

function Button({
  children,
  variant = 'secondary',
  className = '',
  ...props
}) {
  return (
    <button
      className={`button button-${variant} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

function Field({ label, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input {...props} />
    </label>
  );
}

// Вход и регистрация
function AuthPage({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  const submit = e => {
    e.preventDefault();
    setError('');

    if (mode === 'register' && !firstName.trim()) {
      return setError('Укажите имя.');
    }

    if (mode === 'register' && !lastName.trim()) {
      return setError('Укажите фамилию.');
    }

    if (!/^\S+@\S+\.\S+$/.test(email)) {
      return setError('Укажите корректную почту.');
    }

    if (password.length < 6) {
      return setError('Пароль должен содержать минимум 6 символов.');
    }

    if (mode === 'register' && password !== repeat) {
      return setError('Пароли не совпадают.');
    }

    onLogin({
      firstName: mode === 'register' ? firstName.trim() : '',
      lastName: mode === 'register' ? lastName.trim() : '',
      name: mode === 'register'
        ? `${firstName.trim()} ${lastName.trim()}`
        : email.split('@')[0],
      email,
    });
  };

  const switchMode = () => {
    setMode(mode === 'login' ? 'register' : 'login');
    setError('');
    setPassword('');
    setRepeat('');
  };

  return (
    <main className="auth-page">
      <div className="auth-card-shell">
        <div className="auth-card-glow" />

        <section className="auth-panel">
          <Logo />

          <div className="auth-heading">
            <h1>
              {mode === 'login'
                ? 'Вход в Draftly'
                : 'Регистрация'}
            </h1>
          </div>

          <form onSubmit={submit}>
            {mode === 'register' && (
              <>
                <Field
                  label="Имя"
                  value={firstName}
                  onChange={e => setFirstName(e.target.value)}
                  autoComplete="given-name"
                  placeholder="Введите имя"
                  required
                />

                <Field
                  label="Фамилия"
                  value={lastName}
                  onChange={e => setLastName(e.target.value)}
                  autoComplete="family-name"
                  placeholder="Введите фамилию"
                  required
                />
              </>
            )}

            <Field
              label="Электронная почта"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="example@mail.ru"
              required
            />

            <div className="password-field">
              <Field
                label="Пароль"
                type={showPassword ? 'text' : 'password'}
                autoComplete={
                  mode === 'login'
                    ? 'current-password'
                    : 'new-password'
                }
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Не менее 6 символов"
                required
              />

              <button
                className="password-toggle"
                type="button"
                aria-label={
                  showPassword ? 'Скрыть пароль' : 'Показать пароль'
                }
                onClick={() => setShowPassword(v => !v)}
              >
                {showPassword
                  ? <EyeOff size={19} />
                  : <Eye size={19} />}
              </button>
            </div>

            {mode === 'register' && (
              <Field
                label="Повторите пароль"
                type={showPassword ? 'text' : 'password'}
                value={repeat}
                onChange={e => setRepeat(e.target.value)}
                placeholder="Повторите пароль"
                required
              />
            )}

            {error && (
              <p className="form-error" role="alert">
                <AlertCircle size={16} />
                {error}
              </p>
            )}

            <Button variant="primary" type="submit">
              {mode === 'login'
                ? 'Войти'
                : 'Зарегистрироваться'}
            </Button>
          </form>

          <p className="auth-switch">
            {mode === 'login'
              ? 'Нет аккаунта?'
              : 'Уже есть аккаунт?'}{' '}

            <button
              type="button"
              className="text-link"
              onClick={switchMode}
            >
              {mode === 'login'
                ? 'Зарегистрироваться'
                : 'Войти'}
            </button>
          </p>
        </section>
      </div>
    </main>
  );
}

// Навигация
const navigation = [
  { id: 'overview', label: 'Обзор', Icon: House },
  { id: 'analysis', label: 'Результаты анализа', Icon: Sparkles },
  { id: 'drafts', label: 'Черновики', Icon: FileText },
  { id: 'ads', label: 'Мои объявления', Icon: FileCheck2 },
];

// Верхняя панель и боковое меню
function AppHeader({
  user,
  page,
  draftsCount,
  adsCount,
  go,
  onLogout,
}) {
  const [drawer, setDrawer] = useState(false);
  const [profile, setProfile] = useState(false);

  const accountName =
    [user.firstName, user.lastName].filter(Boolean).join(' ') ||
    user.name ||
    user.email ||
    'Пользователь';

  useEffect(() => {
    const close = e => {
      if (e.key === 'Escape') {
        setDrawer(false);
        setProfile(false);
      }
    };

    window.addEventListener('keydown', close);

    return () => window.removeEventListener('keydown', close);
  }, []);

  const navigate = next => {
    go(next);
    setDrawer(false);
    setProfile(false);
  };

  return (
    <>
      <header className="topbar">
        <div className="topbar-left">
          <button
            className="icon-button menu-trigger"
            aria-label="Открыть меню"
            aria-expanded={drawer}
            onClick={() => {
              setDrawer(true);
              setProfile(false);
            }}
          >
            <Menu size={23} />
          </button>

          <Logo small />
        </div>

        <div className="topbar-right">
          <div className="profile-wrap">
            <button
              className="profile-trigger"
              aria-expanded={profile}
              onClick={() => setProfile(v => !v)}
            >
              <span className="avatar">
                <UserRound size={18} />
              </span>

              <span className="profile-name">
                {accountName}
              </span>

              <ChevronDown size={16} />
            </button>

            {profile && (
              <div className="profile-menu">
                <strong>{accountName}</strong>
                <small>{user.email}</small>

                <button
                  onClick={() => {
                    setProfile(false);
                    onLogout();
                  }}
                >
                  <LogOut size={17} />
                  Выйти
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {profile && (
        <button
          className="profile-outside"
          aria-label="Закрыть профиль"
          onClick={() => setProfile(false)}
        />
      )}

      {drawer && (
        <div className="drawer-layer">
          <button
            className="drawer-backdrop"
            aria-label="Закрыть меню"
            onClick={() => setDrawer(false)}
          />

          <aside
            className="navigation-drawer"
            aria-label="Навигация"
          >
            <div className="drawer-header">
              <Logo small />

              <button
                className="icon-button"
                aria-label="Закрыть меню"
                onClick={() => setDrawer(false)}
              >
                <PanelLeftClose size={21} />
              </button>
            </div>

            <p className="drawer-caption">МОЁ ПРОСТРАНСТВО</p>

            <nav>
              {navigation.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  onClick={() => navigate(id)}
                  className={`nav-item ${
                    page === id ? 'active' : ''
                  }`}
                  aria-current={
                    page === id ? 'page' : undefined
                  }
                >
                  <Icon size={20} />
                  <span>{label}</span>

                  {id === 'drafts' && (
                    <small>{draftsCount}</small>
                  )}

                  {id === 'ads' && (
                    <small>{adsCount}</small>
                  )}
                </button>
              ))}
            </nav>

            <div className="drawer-footer">
              <CircleHelp size={19} />
              Черновики остаются у вас до подтверждения.
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

// Иконки категорий
function CategoryIcon({ mcId, size = 25 }) {
  const Icon = icons[mcId] || Wrench;

  return <Icon size={size} strokeWidth={1.8} />;
}

// Обзор
function OverviewPage({
  mcId,
  onMcId,
  description,
  setDescription,
  onAnalyze,
  loading,
  error,
}) {
  return (
    <>
      <div className="page-heading">

        <h1>Создать объявление</h1>
      </div>

      <div className="creation-grid">
        <section
          className="selector-panel"
          aria-labelledby="categories-heading"
        >
          <div className="section-top">
            <h2 id="categories-heading">
              1. Выберите категорию
            </h2>
            <span>6 вариантов</span>
          </div>

          <p className="section-help">
            Услуги → Ремонт и отделка
          </p>

          <div
            className="category-list"
            role="radiogroup"
            aria-label="Исходная микрокатегория"
          >
            {MICROCATEGORIES.map(category => (
              <button
                key={category.mcId}
                type="button"
                role="radio"
                aria-checked={mcId === category.mcId}
                onClick={() => onMcId(category.mcId)}
                className={`category-option ${
                  mcId === category.mcId ? 'selected' : ''
                }`}
              >
                <span className="category-icon">
                  <CategoryIcon
                    mcId={category.mcId}
                    size={22}
                  />
                </span>

                <span className="category-description">
                  <strong>{category.name}</strong>
                </span>

                <span className="category-choice">
                  {mcId === category.mcId
                    ? <Check size={17} />
                    : <ChevronRight size={19} />}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section
          className="description-panel"
          aria-labelledby="description-heading"
        >
          <div className="section-top">
            <h2 id="description-heading">
              2. Опишите объявление
            </h2>
          </div>

          <p className="section-help">
            Текст исходного объявления
          </p>

          {mcId ? (
            <div className="selected-main">
              <ShieldCheck size={17} />

              <span>
                Основная категория:{' '}
                <strong>{categoryFor(mcId)?.name}</strong>
              </span>
            </div>
          ) : (
            <p className="select-hint">
              Сначала выберите категорию слева
            </p>
          )}

          <label
            className="sr-only"
            htmlFor="ad-description"
          >
            Описание услуг
          </label>

          <textarea
            id="ad-description"
            className="description-input"
            value={description}
            maxLength={10000}
            onChange={e => setDescription(e.target.value)}
            placeholder="Например: Делаем ремонт квартир под ключ, а также выполняем сантехнические работы — разводку труб и установку раковин..."
          />

          <div className="input-count">
            {description.length.toLocaleString('ru-RU')} / 10 000 символов
          </div>

          <div className="description-footer">
            <Button
              variant="primary"
              onClick={onAnalyze}
              disabled={
                !mcId ||
                description.trim().length < 12 ||
                loading
              }
            >
              {loading
                ? <LoaderCircle className="spin" size={17} />
                : <Sparkles size={18} />}

              {loading ? 'Загрузка...' : 'Анализировать'}

              <ArrowRight size={17} />
            </Button>
          </div>

          {error && (
            <p role="alert" className="inline-error">
              <AlertCircle size={17} />
              {error}
            </p>
          )}
        </section>
      </div>
    </>
  );
}

// Результаты анализа
function AnalysisPage({
  result,
  onBack,
  onSave,
  proposalStatuses,
  onNew,
  onCopy,
}) {
  if (!result) {
    return (
      <div className="empty-page">
        <Sparkles size={32} />
        <h1>Анализ пока не выполнялся</h1>

        <p>
          Выберите исходную категорию и введите текст объявления.
        </p>

        <Button variant="primary" onClick={onNew}>
          Создать объявление
        </Button>
      </div>
    );
  }

  const source = categoryFor(result.mcId);
  const proposals = result.drafts;

  return (
    <>
      <div className="page-heading">

        <div className="heading-with-action">
          <div>
            <h1>Результаты анализа</h1>
          </div>

          <Button onClick={onNew}>
            <Plus size={17} />
            Новый анализ
          </Button>
        </div>
      </div>

      <section className="result-source">
        <div className="result-source-top">
          <span>Исходное объявление</span>

          <span className="source-main-label">
            <ShieldCheck size={15} />
            Основная: {source?.name}
          </span>
        </div>

        <p>{result.description}</p>
      </section>

      <div className="result-heading">
        <h2>
          Дополнительные микрокатегории
          <span>{proposals.length}</span>
        </h2>
      </div>

      {!proposals.length ? (
        <div className="empty-page empty-inline">
          <CheckCircle2 size={30} />

          <h3>Другие категории не найдены</h3>

          <p>
            Дополнительные черновики не предлагаются.
            Основная категория остаётся прежней.
          </p>
        </div>
      ) : (
        <div className="proposal-list">
          {proposals.map(draft => {
            const category = categoryFor(draft.mcId);
            const status = proposalStatuses.get(draft.mcId);
            const saved = Boolean(status);

            return (
              <article
                className="proposal-card"
                key={draft.mcId}
              >
                <div className="proposal-icon">
                  <CategoryIcon mcId={draft.mcId} size={28} />
                </div>

                <div className="proposal-body">
                  <div className="proposal-kicker">
                    Дополнительная микрокатегория
                  </div>

                  <h3>{category?.name}</h3>

                  {(draft.title || draft.text) && (
                    <div className="suggestion-preview">
                      <strong>
                        {draft.title || category?.name}
                      </strong>
                      <p>{draft.text || ''}</p>
                    </div>
                  )}

                  {result.evidence?.[draft.mcId] && (
                    <p className="evidence">
                      В исходном тексте:
                      «{result.evidence[draft.mcId]}»
                    </p>
                  )}
                </div>

                <div className="proposal-actions">
                  <Button
                    variant={saved ? 'secondary' : 'primary'}
                    disabled={saved}
                    onClick={() => onSave(draft)}
                  >
                    {saved
                      ? <Check size={16} />
                      : <Plus size={16} />}

                    {status === 'ad'
                      ? 'В моих объявлениях'
                      : status === 'draft'
                        ? 'В черновиках'
                        : 'В черновики'}
                  </Button>

                  {draft.title && draft.text && (
                    <button
                      className="tiny-link"
                      onClick={() => onCopy(draft)}
                    >
                      <Copy size={15} />
                      Копировать
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}

// Черновики и мои объявления
function CollectionPage({
  section,
  items,
  onNavigate,
  onEdit,
  onDelete,
  onMove,
  onCopy,
  draftsCount,
  adsCount,
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState('newest');

  const filtered = useMemo(() => {
    return items
      .filter(item => {
        const matchSearch = `${
          item.title || ''
        } ${item.text || ''} ${
          categoryFor(item.mcId)?.name || ''
        }`
          .toLowerCase()
          .includes(query.toLowerCase());

        return matchSearch &&
          (category === 'all' || Number(category) === item.mcId);
      })
      .sort((a, b) => {
        const aa = new Date(
          a.updatedAt || a.createdAt
        ).getTime();

        const bb = new Date(
          b.updatedAt || b.createdAt
        ).getTime();

        return sort === 'newest' ? bb - aa : aa - bb;
      });
  }, [items, query, category, sort]);

  const isAds = section === 'ads';

  return (
    <>
      <div className="page-heading">

        <h1>
          {isAds ? 'Мои объявления' : 'Черновики'}
        </h1>
      </div>

      <div className="collection-toolbar">
        <label className="collection-search">
          <Search size={19} />

          <input
            placeholder="Поиск по объявлениям"
            value={query}
            onChange={e => setQuery(e.target.value)}
            aria-label="Поиск"
          />

          {query && (
            <button
              onClick={() => setQuery('')}
              aria-label="Очистить"
            >
              <X size={16} />
            </button>
          )}
        </label>

        <div className="collection-select">
          <SlidersHorizontal size={17} />

          <select
            value={category}
            aria-label="Категория"
            onChange={e => setCategory(e.target.value)}
          >
            <option value="all">Все категории</option>

            {MICROCATEGORIES.map(cat => (
              <option key={cat.mcId} value={cat.mcId}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>

        <div className="collection-select">
          <Clock3 size={17} />

          <select
            value={sort}
            aria-label="Сортировка"
            onChange={e => setSort(e.target.value)}
          >
            <option value="newest">Сначала новые</option>
            <option value="oldest">Сначала старые</option>
          </select>
        </div>
      </div>

      <p className="results-count">
        Найдено: {filtered.length}
      </p>

      {!filtered.length ? (
        <div className="empty-page empty-inline">
          <FileText size={32} />

          <h3>
            {items.length
              ? 'Ничего не найдено'
              : isAds
                ? 'Пока нет объявлений'
                : 'Пока нет черновиков'}
          </h3>

          <p>
            {items.length
              ? 'Попробуйте изменить условия поиска.'
              : 'После анализа текста вы сможете сохранить предложения сюда.'}
          </p>

          <Button
            onClick={() => {
              if (items.length) {
                setQuery('');
                setCategory('all');
              } else {
                onNavigate('overview');
              }
            }}
          >
            {items.length
              ? 'Сбросить фильтры'
              : 'Создать объявление'}
          </Button>
        </div>
      ) : (
        <div className="collection-list">
          {filtered.map(item => (
            <article className="listing" key={item.id}>
              <div className="listing-body">
                <div className="listing-caption">
                  <span
                    className={
                      isAds
                        ? 'listing-status ready'
                        : 'listing-status'
                    }
                  >
                    {isAds
                      ? 'Готово к публикации'
                      : 'Черновик'}
                  </span>

                  <span>
                    {new Date(
                      item.updatedAt || item.createdAt
                    ).toLocaleDateString('ru-RU')}
                  </span>
                </div>

                <h3>
                  {item.title ||
                    categoryFor(item.mcId)?.name ||
                    'Без названия'}
                </h3>

                <p className="listing-micro">
                  Услуги · Ремонт и отделка ·{' '}
                  {categoryFor(item.mcId)?.name}
                </p>

                <p className="listing-text">
                  {item.text ||
                    'Описание пока не заполнено.'}
                </p>

                <div className="listing-actions">
                  <button onClick={() => onEdit(item)}>
                    <Pencil size={16} />
                    Редактировать
                  </button>

                  {item.title && item.text && (
                    <button onClick={() => onCopy(item)}>
                      <Copy size={16} />
                      Скопировать
                    </button>
                  )}

                  <button onClick={() => onMove(item)}>
                    {isAds
                      ? <ArrowLeft size={16} />
                      : <CheckCircle2 size={16} />}

                    {isAds
                      ? 'В черновики'
                      : 'В мои объявления'}
                  </button>

                  <button
                    className="delete-link"
                    onClick={() => onDelete(item)}
                  >
                    <Trash2 size={16} />
                    Удалить
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

// Редактирование объявления
function EditModal({ item, onClose, onSave }) {
  const [title, setTitle] = useState(item.title || '');
  const [text, setText] = useState(item.text || '');
  const [error, setError] = useState('');

  useEffect(() => {
    const listener = e => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [onClose]);

  const submit = e => {
    e.preventDefault();

    if (!title.trim() || !text.trim()) {
      return setError(
        'Заполните заголовок и текст объявления.'
      );
    }

    onSave({
      ...item,
      title: title.trim(),
      text: text.trim(),
      updatedAt: new Date().toISOString(),
    });
  };

  return (
    <div
      className="modal-layer"
      onMouseDown={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-title"
      >
        <div className="modal-head">
          <div>
            <h2 id="edit-title">
              Редактирование объявления
            </h2>

            <p>{categoryFor(item.mcId)?.name}</p>
          </div>

          <button
            className="icon-button"
            aria-label="Закрыть"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={submit}>
          <label className="field">
            <span>Заголовок</span>

            <input
              value={title}
              maxLength={110}
              onChange={e => setTitle(e.target.value)}
              placeholder="Название объявления"
            />
          </label>

          <label className="field">
            <span>Описание</span>

            <textarea
              value={text}
              rows={7}
              onChange={e => setText(e.target.value)}
              placeholder="Укажите только реальные услуги и условия"
            />
          </label>

          {error && (
            <p className="inline-error">{error}</p>
          )}

          <div className="modal-actions">
            <Button type="button" onClick={onClose}>
              Отмена
            </Button>

            <Button type="submit" variant="primary">
              <Check size={16} />
              Сохранить
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}

// Основное приложение
function App() {
  const [user, setUser] = useState(
    initial.user || previous.user || null
  );

  const [page, setPage] = useState('overview');

  const [mcId, setMcId] = useState(
    initial.mcId || null
  );

  const [description, setDescription] = useState(
    initial.description || ''
  );

  const [result, setResult] = useState(
    initial.result || null
  );

  const [drafts, setDrafts] = useState(
    initial.drafts || []
  );

  const [ads, setAds] = useState(
    initial.ads || []
  );

  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [editItem, setEditItem] = useState(null);

  useEffect(() => {
    localStorage.setItem(
      STORAGE,
      JSON.stringify({
        user,
        mcId,
        description,
        result,
        drafts,
        ads,
      })
    );
  }, [user, mcId, description, result, drafts, ads]);

  useEffect(() => {
    if (!toast) return undefined;

    const id = setTimeout(() => setToast(''), 3200);
    return () => clearTimeout(id);
  }, [toast]);

  const notify = message => setToast(message);

  const go = next => {
    setPage(next);
    setError('');

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  };

  // Пока используется заглушка
  const onAnalyze = () => {
    setError('');

    if (!categoryFor(mcId)) {
      setError('Выберите исходную микрокатегорию.');
      return;
    }

    if (description.trim().length < 12) {
      setError('Введите описание не короче 12 символов.');
      return;
    }

    const response = getMockResults(mcId);

    setResult({
      ...response,
      mcId,
      description,
      date: new Date().toISOString(),
    });

    go('analysis');
  };

  const saveProposal = proposal => {
    if (
      !result ||
      proposal.mcId === result.mcId ||
      !categoryFor(proposal.mcId)
    ) {
      return;
    }

    if (
      drafts.some(
        d =>
          d.sourceId === result.date &&
          d.mcId === proposal.mcId
      ) ||
      ads.some(
        d =>
          d.sourceId === result.date &&
          d.mcId === proposal.mcId
      )
    ) {
      return;
    }

    const record = {
      id: crypto.randomUUID(),
      sourceId: result.date,
      mcId: proposal.mcId,
      sourceMcId: result.mcId,
      title: proposal.title || '',
      text: proposal.text || '',
      createdAt: new Date().toISOString(),
    };

    setDrafts(prev => [record, ...prev]);

    notify(
      'Черновик сохранён. Проверьте и при необходимости заполните текст.'
    );
  };

  const deleteItem = item => {
    if (!window.confirm('Удалить объявление?')) return;

    setDrafts(prev =>
      prev.filter(d => d.id !== item.id)
    );

    setAds(prev =>
      prev.filter(d => d.id !== item.id)
    );

    notify('Объявление удалено');
  };

  const moveItem = (item, from) => {
    if (from === 'drafts') {
      if (!item.title?.trim() || !item.text?.trim()) {
        setEditItem(item);
        notify(
          'Для переноса заполните заголовок и описание.'
        );
        return;
      }

      setDrafts(prev =>
        prev.filter(d => d.id !== item.id)
      );

      setAds(prev => [
        {
          ...item,
          updatedAt: new Date().toISOString(),
        },
        ...prev,
      ]);

      notify('Добавлено в «Мои объявления»');
    } else {
      setAds(prev =>
        prev.filter(d => d.id !== item.id)
      );

      setDrafts(prev => [
        {
          ...item,
          updatedAt: new Date().toISOString(),
        },
        ...prev,
      ]);

      notify('Перенесено в черновики');
    }
  };

  const saveEdit = item => {
    setDrafts(prev =>
      prev.map(d => d.id === item.id ? item : d)
    );

    setAds(prev =>
      prev.map(d => d.id === item.id ? item : d)
    );

    setEditItem(null);
    notify('Изменения сохранены');
  };

  const copy = async item => {
    try {
      await navigator.clipboard.writeText(
        `${item.title}\n\n${item.text}`
      );

      notify('Объявление скопировано');
    } catch {
      notify('Не удалось скопировать текст.');
    }
  };

  const proposalStatuses = useMemo(() => {
    const statuses = new Map();

    if (!result) return statuses;

    drafts
      .filter(item => item.sourceId === result.date)
      .forEach(item => {
        statuses.set(item.mcId, 'draft');
      });

    ads
      .filter(item => item.sourceId === result.date)
      .forEach(item => {
        statuses.set(item.mcId, 'ad');
      });

    return statuses;
  }, [drafts, ads, result]);

  if (!user) {
    return <AuthPage onLogin={setUser} />;
  }

  return (
    <div className="app-shell">
      <AppHeader
        user={user}
        page={page}
        go={go}
        draftsCount={drafts.length}
        adsCount={ads.length}
        onLogout={() => {
          setUser(null);
          go('overview');
        }}
      />

      <main className="main-content">
        {page === 'overview' && (
          <OverviewPage
            mcId={mcId}
            onMcId={setMcId}
            description={description}
            setDescription={setDescription}
            onAnalyze={onAnalyze}
            loading={false}
            error={error}
          />
        )}

        {page === 'analysis' && (
          <AnalysisPage
            result={result}
            onBack={() => go('overview')}
            onNew={() => {
              setResult(null);
              setMcId(null);
              setDescription('');
              go('overview');
            }}
            onSave={saveProposal}
            proposalStatuses={proposalStatuses}
            onCopy={copy}
          />
        )}

        {(page === 'drafts' || page === 'ads') && (
          <CollectionPage
            key={page}
            section={page}
            items={page === 'drafts' ? drafts : ads}
            onNavigate={go}
            onEdit={setEditItem}
            onDelete={deleteItem}
            onMove={item => moveItem(item, page)}
            onCopy={copy}
            draftsCount={drafts.length}
            adsCount={ads.length}
          />
        )}
      </main>

      {toast && (
        <div className="toast">
          <CheckCircle2 size={17} />
          {toast}
        </div>
      )}

      {editItem && (
        <EditModal
          item={editItem}
          onClose={() => setEditItem(null)}
          onSave={saveEdit}
        />
      )}
    </div>
  );
}

export default App;