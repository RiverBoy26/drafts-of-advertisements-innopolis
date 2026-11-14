import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  analyzeText, changeDraftState, deleteDraft, getMicrocategories, getProfile,
  listDrafts, login, logout, refresh, register, updateDraft,
} from './api';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Copy,
  FileCheck2,
  FileText,
  Grid3X3,
  House,
  LogOut,
  Menu,
  Paintbrush,
  PaintRoller,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Wrench,
  X,
  AlertCircle,
  LoaderCircle,
  Eye,
  EyeOff,
  PanelLeftClose,
  UserRound,
  Zap,
  SlidersHorizontal,
  Clock3,
} from 'lucide-react';

const SESSION_STORAGE = 'draftly-session-v1';

function safeRead(key) {
  try {
    return JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return {};
  }
}

const categoryFor = (mcId, categories) =>
  categories.find(c => c.mcId === Number(mcId));

const icons = {
  101: House,
  102: PaintRoller,
  103: Grid3X3,
  104: Wrench,
  105: Zap,
  106: Paintbrush,
};

// Логотип
function Logo({ small = false }) {
  return (
    <span className={`brand ${small ? 'brand-small' : ''}`}>
      <img src="/logo_draftly.png" alt="Draftly" />
    </span>
  );
}

// Общая кнопка
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

// Поле ввода
function Field({ label, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input {...props} />
    </label>
  );
}

// Вход и регистрация
function AuthPage({ onLogin, connectionError }) {
  const [mode, setMode] = useState('login');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async e => {
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

    if (mode === 'register' && password.length < 8) {
      return setError('Пароль должен содержать минимум 8 символов.');
    }

    if (mode === 'register' && password !== repeat) {
      return setError('Пароли не совпадают.');
    }

    setLoading(true);
    try {
      await onLogin(mode, {
        ...(mode === 'register' ? { firstName: firstName.trim(), lastName: lastName.trim() } : {}),
        email: email.trim(),
        password,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
              {mode === 'login' ? 'Вход в Draftly' : 'Регистрация'}
            </h1>

            <p>Ваши объявления — в одном месте</p>
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
                placeholder="Не менее 8 символов"
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

          {(error || connectionError) && (
              <p className="form-error" role="alert">
                <AlertCircle size={16} />
                {error || connectionError}
              </p>
            )}

            <Button variant="primary" type="submit" disabled={loading}>
              {loading ? 'Подождите...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </Button>
          </form>

          <p className="auth-switch">
            {mode === 'login' ? 'Нет аккаунта?' : 'Уже есть аккаунт?'}{' '}

            <button
              type="button"
              className="text-link"
              onClick={switchMode}
            >
              {mode === 'login' ? 'Зарегистрироваться' : 'Войти'}
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
          <button
            className="topbar-create"
            onClick={() => navigate('overview')}
          >
            <Plus size={17} />
            Новое объявление
          </button>

          <div className="profile-wrap">
            <button
              className="profile-trigger"
              aria-expanded={profile}
              onClick={() => setProfile(v => !v)}
            >
              <span className="avatar">
                <UserRound size={18} />
              </span>

              <span>Аккаунт</span>
              <ChevronDown size={16} />
            </button>

            {profile && (
              <div className="profile-menu">
                <strong>{user.name}</strong>
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
                  className={`nav-item ${page === id ? 'active' : ''}`}
                  aria-current={page === id ? 'page' : undefined}
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

// Иконки микрокатегорий
function CategoryIcon({ mcId, size = 25 }) {
  const Icon = icons[mcId] || Wrench;

  return <Icon size={size} strokeWidth={1.8} />;
}

// Обзор
function OverviewPage({
  categories,
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
        <p className="breadcrumb">
          Главная
          <ChevronRight size={14} />
          Услуги
          <ChevronRight size={14} />
          Ремонт и отделка
        </p>

        <h1>Создать объявление</h1>
      </div>

      <div className="creation-grid">
        <section
          className="selector-panel"
          aria-labelledby="categories-heading"
        >
          <div className="section-top">
            <h2 id="categories-heading">1. Выберите категорию</h2>
            <span>{categories.length} вариантов</span>
          </div>

          <p className="section-help">
            Услуги → Ремонт и отделка
          </p>

          <div
            className="category-list"
            role="radiogroup"
            aria-label="Исходная микрокатегория"
          >
            {categories.map(category => (
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
                <strong>{categoryFor(mcId, categories)?.name}</strong>
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

// Страница результатов
function AnalysisPage({
  categories,
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

  const source = categoryFor(result.mcId, categories);
  const proposals = result.drafts;

  return (
    <>
      <div className="page-heading">
        <p className="breadcrumb">
          <button onClick={onBack}>Обзор</button>
          <ChevronRight size={14} />
          Результаты анализа
        </p>

        <div className="heading-with-action">
          <div>
            <h1>Результаты анализа</h1>

            <p>
              Проверьте предложения и сохраните подходящие черновики.
            </p>
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
            const category = categoryFor(draft.mcId, categories);
            const status = proposalStatuses.get(draft.mcId);
            const saved = Boolean(status);

            return (
              <article
                className="proposal-card"
                key={draft.mcId}
              >
                <div className="proposal-icon">
                  <CategoryIcon
                    mcId={draft.mcId}
                    size={28}
                  />
                </div>

                <div className="proposal-body">
                  <div className="proposal-kicker">
                    Дополнительная микрокатегория
                  </div>

                  <h3>{category?.name}</h3>

                  {draft.title || draft.text ? (
                    <div className="suggestion-preview">
                      <strong>
                        {draft.title || 'Без заголовка'}
                      </strong>

                      <p>
                        {draft.text ||
                          'Текст необходимо заполнить вручную.'}
                      </p>
                    </div>
                  ) : (
                    <p className="suggestion-unfilled">
                      Заголовок и описание можно добавить в черновике.
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
  categories,
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
        const matchSearch = `
          ${item.title || ''}
          ${item.text || ''}
          ${categoryFor(item.mcId, categories)?.name || ''}
        `
          .toLowerCase()
          .includes(query.toLowerCase());

        return matchSearch && (
          category === 'all' ||
          Number(category) === item.mcId
        );
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
  }, [items, query, category, sort, categories]);

  const isAds = section === 'ads';

  return (
    <>
      <div className="page-heading">
        <p className="breadcrumb">
          Моё пространство
          <ChevronRight size={14} />
          {isAds ? 'Мои объявления' : 'Черновики'}
        </p>

        <div className="heading-with-action">
          <div>
            <h1>
              {isAds ? 'Мои объявления' : 'Черновики'}
            </h1>

            <p>
              {isAds
                ? 'Подготовленные объявления, которые можно скопировать для публикации.'
                : 'Сохранённые варианты — проверьте и отредактируйте перед использованием.'}
            </p>
          </div>

          <Button
            variant="primary"
            onClick={() => onNavigate('overview')}
          >
            <Plus size={17} />
            Создать объявление
          </Button>
        </div>
      </div>

      <div className="collection-tabs">
        <button
          className={!isAds ? 'active' : ''}
          onClick={() => onNavigate('drafts')}
        >
          Черновики <span>{draftsCount}</span>
        </button>

        <button
          className={isAds ? 'active' : ''}
          onClick={() => onNavigate('ads')}
        >
          Мои объявления <span>{adsCount}</span>
        </button>
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
            <option value="all">
              Все категории
            </option>

            {categories.map(cat => (
              <option
                key={cat.mcId}
                value={cat.mcId}
              >
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
            <article
              className="listing"
              key={item.id}
            >
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
                    categoryFor(item.mcId, categories)?.name ||
                    'Без названия'}
                </h3>

                <p className="listing-micro">
                  Услуги · Ремонт и отделка ·{' '}
                  {categoryFor(item.mcId, categories)?.name}
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
function EditModal({ item, categories, onClose, onSave }) {
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
              Редактирование черновика
            </h2>

            <p>
              {categoryFor(item.mcId, categories)?.name}
            </p>
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
  const [session, setSession] = useState(() => safeRead(SESSION_STORAGE));
  const sessionRef = useRef(session);
  const user = session?.user || null;
  const [categories, setCategories] = useState([]);
  const [page, setPage] = useState('overview');
  const [mcId, setMcId] = useState(null);
  const [description, setDescription] = useState('');
  const [result, setResult] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [ads, setAds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [editItem, setEditItem] = useState(null);

  useEffect(() => {
    sessionRef.current = session;
    if (session?.accessToken) {
      localStorage.setItem(SESSION_STORAGE, JSON.stringify(session));
    } else {
      localStorage.removeItem(SESSION_STORAGE);
    }
  }, [session]);

  useEffect(() => {
    getMicrocategories().then(setCategories).catch(err => setError(err.message));
  }, []);

  useEffect(() => {
    if (!session?.accessToken) return;
    let active = true;
    Promise.all([
      getProfile(session.accessToken),
      listDrafts('draft', session.accessToken),
      listDrafts('ready', session.accessToken),
    ]).then(([profile, savedDrafts, savedAds]) => {
      if (!active) return;
      setSession(current => ({ ...current, user: profile }));
      setDrafts(savedDrafts);
      setAds(savedAds);
    }).catch(async err => {
      if (!active) return;
      if (err.status === 401 && session.refreshToken) {
        try {
          const renewed = await refresh(session.refreshToken);
          if (active) {
            sessionRef.current = renewed;
            setSession(renewed);
          }
          return;
        } catch (refreshError) {
          if (active) setError(refreshError.message);
        }
      } else {
        setError(err.message);
        if (err.status !== 401) return;
      }
      sessionRef.current = null;
      setSession(null);
    });
    return () => { active = false; };
  }, [session?.accessToken]);

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

  const authorized = async action => {
    const current = sessionRef.current;
    try {
      return await action(current.accessToken);
    } catch (err) {
      if (err.status !== 401 || !current.refreshToken) throw err;
      const renewed = await refresh(current.refreshToken);
      sessionRef.current = renewed;
      setSession(renewed);
      return action(renewed.accessToken);
    }
  };

  const loadCollections = async () => {
    const [savedDrafts, savedAds] = await authorized(token => Promise.all([
      listDrafts('draft', token), listDrafts('ready', token),
    ]));
    setDrafts(savedDrafts);
    setAds(savedAds);
  };

  const onAuth = async (mode, credentials) => {
    const response = mode === 'register' ? await register(credentials) : await login(credentials);
    sessionRef.current = response;
    setSession(response);
    setError('');
    go('overview');
  };

  const onAnalyze = async () => {
    setError('');
    if (!categoryFor(mcId, categories)) return setError('Выберите исходную микрокатегорию.');
    if (description.trim().length < 12) return setError('Введите описание не короче 12 символов.');
    setLoading(true);
    try {
      const analysis = await authorized(token => analyzeText(description.trim(), mcId, token));
      setResult(analysis);
      go('analysis');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const saveProposal = async proposal => {
    try {
      const updated = await authorized(token => changeDraftState(proposal.id, 'draft', token));
      setResult(prev => ({ ...prev, drafts: prev.drafts.map(item => item.id === updated.id ? updated : item) }));
      await loadCollections();
      notify('Черновик сохранён. Проверьте и при необходимости заполните текст.');
    } catch (err) {
      notify(err.message);
    }
  };

  const deleteItem = async item => {
    if (!window.confirm('Удалить объявление?')) return;
    try {
      await authorized(token => deleteDraft(item.id, token));
      setResult(prev => prev ? { ...prev, drafts: prev.drafts.filter(d => d.id !== item.id) } : prev);
      await loadCollections();
      notify('Объявление удалено');
    } catch (err) {
      notify(err.message);
    }
  };

  const moveItem = async (item, from) => {
    if (from === 'drafts' && (!item.title?.trim() || !item.text?.trim())) {
      setEditItem(item);
      notify('Для переноса заполните заголовок и описание.');
      return;
    }
    try {
      const state = from === 'drafts' ? 'ready' : 'draft';
      const updated = await authorized(token => changeDraftState(item.id, state, token));
      setResult(prev => prev ? { ...prev, drafts: prev.drafts.map(d => d.id === item.id ? updated : d) } : prev);
      await loadCollections();
      notify(from === 'drafts' ? 'Добавлено в «Мои объявления»' : 'Перенесено в черновики');
    } catch (err) {
      notify(err.message);
    }
  };

  const saveEdit = async item => {
    try {
      const updated = await authorized(token => updateDraft(item, token));
      setResult(prev => prev ? { ...prev, drafts: prev.drafts.map(d => d.id === item.id ? updated : d) } : prev);
      await loadCollections();
      setEditItem(null);
      notify('Изменения сохранены');
    } catch (err) {
      notify(err.message);
    }
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
    result?.drafts.forEach(item => {
      if (item.collectionState === 'draft') statuses.set(item.mcId, 'draft');
      if (item.collectionState === 'ready') statuses.set(item.mcId, 'ad');
    });
    return statuses;
  }, [result]);

  if (!user) {
    return <AuthPage onLogin={onAuth} connectionError={error} />;
  }

  return (
    <div className="app-shell">
      <AppHeader
        user={{ ...user, name: `${user.firstName} ${user.lastName}`.trim() }}
        page={page}
        go={go}
        draftsCount={drafts.length}
        adsCount={ads.length}
        onLogout={async () => {
          try { await logout(session.refreshToken); } catch { /* Local sign-out still applies. */ }
          sessionRef.current = null;
          setSession(null);
          setDrafts([]);
          setAds([]);
          setResult(null);
          go('overview');
        }}
      />

      <main className="main-content">
        {page === 'overview' && (
          <OverviewPage
            categories={categories}
            mcId={mcId}
            onMcId={setMcId}
            description={description}
            setDescription={setDescription}
            onAnalyze={onAnalyze}
            loading={loading}
            error={error}
          />
        )}

        {page === 'analysis' && (
          <AnalysisPage
            categories={categories}
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
            categories={categories}
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
          categories={categories}
          onClose={() => setEditItem(null)}
          onSave={saveEdit}
        />
      )}
    </div>
  );
}

export default App;
