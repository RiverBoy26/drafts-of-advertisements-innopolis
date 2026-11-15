
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight, Check, CheckCircle2, ChevronDown, CircleHelp,
  Copy, FileSpreadsheet, FileText, House, LogOut, Menu, PanelLeftClose,
  Pencil, Search, ShieldCheck, Sparkles, Trash2, UploadCloud, UserRound,
  X, AlertCircle, Eye, EyeOff, SlidersHorizontal, Clock3, Plus,
} from 'lucide-react';
import { analyzeText, deleteAllDrafts, deleteDraft as removeDraft, listDrafts, login, logout, register, updateDraft } from './api.js';

const MICROCATEGORIES = [
  { mcId: 101, name: 'Ремонт под ключ' },
  { mcId: 102, name: 'Штукатурные работы' },
  { mcId: 103, name: 'Плиточные работы' },
  { mcId: 104, name: 'Сантехника' },
  { mcId: 105, name: 'Электрика' },
  { mcId: 106, name: 'Поклейка обоев и малярные работы' },
];

const MAIN_CATEGORY_ID = 101;

const categoryFor = id =>
  MICROCATEGORIES.find(c => c.mcId === Number(id));

const pluralRu = (count, one, few, many) => {
  const mod100 = count % 100;
  const mod10 = count % 10;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
};

// CSV-парсер. Поддерживает запятую и точку с запятой,
// текст в кавычках и переносы строк.
function parseCsv(content) {
  const source = content.replace(/^\uFEFF/, '');
  const firstLine = source.split(/\r?\n/).find(line => line.trim()) || '';
  const separator = firstLine.includes(';') ? ';' : ',';

  const rows = [];
  let currentRow = [];
  let value = '';
  let quoted = false;

  const finishValue = () => {
    currentRow.push(value);
    value = '';
  };

  const finishRow = () => {
    finishValue();

    if (currentRow.some(cell => cell.trim())) {
      rows.push(currentRow);
    }

    currentRow = [];
  };

  for (let i = 0; i < source.length; i++) {
    const ch = source[i];

    if (ch === '"') {
      if (quoted && source[i + 1] === '"') {
        value += '"';
        i++;
      } else {
        quoted = !quoted;
      }
    } else if (ch === separator && !quoted) {
      finishValue();
    } else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && source[i + 1] === '\n') {
        i++;
      }

      finishRow();
    } else {
      value += ch;
    }
  }

  if (quoted) {
    throw new Error('В CSV есть незакрытые кавычки.');
  }

  if (value || currentRow.length) {
    finishRow();
  }

  if (rows.length < 2) {
    throw new Error(
      'CSV должен содержать заголовки и хотя бы одну строку данных.'
    );
  }

  const headers = rows[0].map(v => v.trim().toLowerCase());

  const idIndex = headers.findIndex(h =>
    ['id', 'ид'].includes(h)
  );

  const descriptionIndex = headers.findIndex(h =>
    ['description', 'описание', 'text', 'текст'].includes(h)
  );

  if (idIndex < 0 || descriptionIndex < 0) {
    throw new Error(
      'В CSV нужны два столбца: id и description.'
    );
  }

  const seenIds = new Set();

  const records = rows.slice(1).map((cols, index) => {
    const id = (cols[idIndex] || '').trim();
    const description = (cols[descriptionIndex] || '').trim();

    if (!id || !description) {
      throw new Error(
        `В строке ${index + 2} не заполнен id или description.`
      );
    }

    if (seenIds.has(id)) {
      throw new Error(`Повторяется id «${id}».`);
    }

    seenIds.add(id);

    return { id, description };
  });

  if (records.length > 100) {
    throw new Error(
      'Для предпросмотра загрузите не более 100 записей.'
    );
  }

  return records;
}

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
    setMode(v => v === 'login' ? 'register' : 'login');
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
                  mode === 'login' ? 'current-password' : 'new-password'
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

            <Button variant="primary" type="submit">
              {mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
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

// Только два раздела в меню
const navigation = [
  { id: 'overview', label: 'Обзор', Icon: House },
  { id: 'drafts', label: 'Черновики', Icon: FileText },
];

// Верхняя панель
function AppHeader({
  user,
  page,
  draftsCount,
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
                  aria-current={page === id ? 'page' : undefined}
                >
                  <Icon size={20} />
                  <span>{label}</span>

                  {id === 'drafts' && (
                    <small>{draftsCount}</small>
                  )}
                </button>
              ))}
            </nav>

            <div className="drawer-footer">
              <CircleHelp size={19} />
              С любовью, Команда 404! С хрумками и газявой!!!
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

// Главная страница: текст или CSV
function OverviewPage({
  inputMode,
  setInputMode,
  description,
  setDescription,
  records,
  setRecords,
  fileName,
  setFileName,
  onAnalyze,
  error,
  analyzing,
}) {
  const fileInput = useRef(null);
  const [drag, setDrag] = useState(false);
  const [fileError, setFileError] = useState('');

  const acceptFile = async file => {
    if (!file) return;

    setFileError('');

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setRecords([]);
      setFileName('');
      setFileError('Выберите файл формата .csv');
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setRecords([]);
      setFileName('');
      setFileError('Размер файла не должен превышать 2 МБ.');
      return;
    }

    try {
      const data = parseCsv(await file.text());

      setRecords(data);
      setFileName(file.name);
      setInputMode('csv');
    } catch (e) {
      setRecords([]);
      setFileName('');
      setFileError(e.message);
    }

    if (fileInput.current) {
      fileInput.current.value = '';
    }
  };

  return (
    <div className="create-page">
      <div className="page-heading">
        <h1>Создать объявление</h1>
      </div>

      <section className="input-panel">
        <div className="input-panel-heading">
          <h2>Добавьте описание услуг</h2>
        </div>

        <div
          className="input-mode-tabs"
          role="tablist"
          aria-label="Способ ввода"
        >
          <button
            role="tab"
            aria-selected={inputMode === 'text'}
            className={inputMode === 'text' ? 'active' : ''}
            onClick={() => setInputMode('text')}
          >
            <FileText size={19} />
            Ввести текст
          </button>

          <button
            role="tab"
            aria-selected={inputMode === 'csv'}
            className={inputMode === 'csv' ? 'active' : ''}
            onClick={() => setInputMode('csv')}
          >
            <FileSpreadsheet size={19} />
            Загрузить CSV
          </button>
        </div>

        {inputMode === 'text' ? (
          <div className="text-input-view" role="tabpanel">
            <label
              className="input-caption"
              htmlFor="ad-description"
            >
              Описание объявления
            </label>

            <textarea
              id="ad-description"
              className="description-input"
              maxLength={10000}
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Например: Выполняем ремонт квартир под ключ, устанавливаем сантехнику, проводим электромонтажные работы..."
            />

            <div className="input-count">
              {description.length.toLocaleString('ru-RU')} / 10 000 символов
            </div>
          </div>
        ) : (
          <div className="csv-input-view" role="tabpanel">
            <input
              className="sr-only"
              ref={fileInput}
              type="file"
              accept=".csv,text/csv"
              aria-label="Выбрать CSV-файл"
              onChange={e => acceptFile(e.target.files?.[0])}
            />

            <div
              className={`upload-zone ${drag ? 'dragging' : ''}`}
              onDragOver={e => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={e => {
                e.preventDefault();
                setDrag(false);
              }}
              onDrop={e => {
                e.preventDefault();
                setDrag(false);
                acceptFile(e.dataTransfer.files?.[0]);
              }}
            >
              <span className="upload-icon">
                <UploadCloud size={27} />
              </span>

              <strong>Перетащите CSV-файл сюда</strong>
              <p>или выберите его с компьютера</p>

              <Button
                onClick={() => fileInput.current?.click()}
              >
                Выбрать файл
              </Button>

              <span className="upload-format">
                Столбцы: id, description · до 2 МБ
              </span>
            </div>

            {fileError && (
              <p className="inline-error" role="alert">
                <AlertCircle size={17} />
                {fileError}
              </p>
            )}

            {records.length > 0 && (
              <div className="csv-preview">
                <div className="csv-preview-header">
                  <span className="csv-file-symbol">
                    <FileSpreadsheet size={22} />
                  </span>

                  <div>
                    <strong>{fileName}</strong>
                    <small>{records.length} записей</small>
                  </div>

                  <CheckCircle2
                    size={19}
                    className="success-icon"
                  />

                  <button
                    className="icon-button"
                    aria-label="Удалить файл"
                    onClick={() => {
                      setRecords([]);
                      setFileName('');
                    }}
                  >
                    <X size={18} />
                  </button>
                </div>

                <div className="csv-table-scroll">
                  <table className="csv-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Описание</th>
                      </tr>
                    </thead>

                    <tbody>
                      {records.slice(0, 5).map((record, index) => (
                        <tr key={`${record.id}-${index}`}>
                          <td>{record.id}</td>
                          <td>{record.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {records.length > 5 && (
                  <p className="csv-more">
                    И ещё {records.length - 5} записей
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        <div className="input-panel-footer">
          <Button
            className="analyze-button"
            variant="primary"
            onClick={onAnalyze}
            disabled={
              analyzing || (inputMode === 'text'
                ? description.trim().length < 12
                : records.length === 0)
            }
          >
            <Sparkles size={19} />
            {analyzing ? 'Анализируем…' : 'Анализировать'}
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
  );
}

// Страница «Черновики»
function DraftsPage({
  items,
  analysis,
  onNew,
  onEdit,
  onDelete,
  onDeleteAll,
  onCopy,
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState('newest');

  // Начинаем с исходных объявлений последнего анализа. Благодаря этому
  // видны даже объявления, для которых не удалось найти ни одной категории.
  const allGroups = useMemo(() => {
    const bySource = new Map();

    (analysis?.groups || []).forEach((source, index) => {
      bySource.set(source.sourceKey, {
        key: source.sourceKey,
        number: index + 1,
        sourceId: source.id,
        description: source.description,
        hadGeneratedDrafts: (source.proposals || []).length > 0,
        drafts: [],
      });
    });

    [...items]
      .sort((a, b) => (Date.parse(a.createdAt) || 0) - (Date.parse(b.createdAt) || 0))
      .forEach(item => {
        const key = item.sourceKey || item.sourceAdId || item.analysisId || item.id;

        if (!bySource.has(key)) {
          bySource.set(key, {
            key,
            number: item.sourceIndex || bySource.size + 1,
            sourceId: item.sourceId || null,
            description: item.sourceDescription || '',
            hadGeneratedDrafts: true,
            drafts: [],
          });
        }

        const group = bySource.get(key);
        if (!group.description && item.sourceDescription) {
          group.description = item.sourceDescription;
        }
        group.drafts.push(item);
      });

    return [...bySource.values()];
  }, [items, analysis]);

  const foundCategories = useMemo(() => {
    return allGroups.reduce((sum, group) => {
      const ids = group.drafts
        .map(draft => Number(draft.mcId))
        .filter(Number.isFinite);
      return sum + new Set(ids).size;
    }, 0);
  }, [allGroups]);

  const visibleGroups = useMemo(() => {
    const term = query.trim().toLowerCase();

    return allGroups
      .map(group => {
        const sourceMatches = !term ||
          `${group.description} ${group.sourceId || ''}`.toLowerCase().includes(term);

        const drafts = group.drafts.filter(item => {
          if (category !== 'all' && Number(category) !== Number(item.mcId)) {
            return false;
          }
          if (sourceMatches) return true;
          const content = `${item.title || ''} ${item.text || ''} ${categoryFor(item.mcId)?.name || ''}`;
          return content.toLowerCase().includes(term);
        });

        if (category !== 'all' && drafts.length === 0) return null;
        if (term && !sourceMatches && drafts.length === 0) return null;
        return { ...group, drafts };
      })
      .filter(Boolean)
      .sort((a, b) => sort === 'newest' ? b.number - a.number : a.number - b.number);
  }, [allGroups, query, category, sort]);

  const visibleDraftsCount = visibleGroups.reduce((sum, group) => sum + group.drafts.length, 0);
  const processedCount = analysis ? analysis.groups.length : allGroups.length;

  return (
    <>
      <div className="page-heading">
        <h1>Черновики</h1>
      </div>

      <div className="drafts-summary" aria-label="Итоги анализа">
        <div className="drafts-summary-card">
          <span>Обработано объявлений</span>
          <strong>{processedCount}</strong>
        </div>
        <div className="drafts-summary-card">
          <span>Найдено категорий</span>
          <strong>{foundCategories}</strong>
        </div>
        <div className="drafts-summary-card">
          <span>Создано черновиков</span>
          <strong>{items.length}</strong>
        </div>
      </div>

      <div className="collection-toolbar">
        <label className="collection-search">
          <Search size={19} />
          <input
            placeholder="Поиск по черновикам"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          {query && (
            <button type="button" aria-label="Очистить поиск" onClick={() => setQuery('')}>
              <X size={16} />
            </button>
          )}
        </label>

        <div className="collection-select">
          <SlidersHorizontal size={17} />
          <select
            value={category}
            onChange={e => setCategory(e.target.value)}
            aria-label="Микрокатегория"
          >
            <option value="all">Все категории</option>
            {MICROCATEGORIES.map(c => (
              <option key={c.mcId} value={c.mcId}>{c.name}</option>
            ))}
          </select>
        </div>

        <div className="collection-select">
          <Clock3 size={17} />
          <select
            aria-label="Сортировка"
            value={sort}
            onChange={e => setSort(e.target.value)}
          >
            <option value="newest">Сначала новые</option>
            <option value="oldest">Сначала старые</option>
          </select>
        </div>

        <Button
          type="button"
          className="button-danger-outline delete-all-button"
          onClick={onDeleteAll}
          disabled={!items.length}
        >
          <Trash2 size={16} /> Удалить все черновики
        </Button>
      </div>

      <p className="results-count">
        Показано исходных объявлений: {visibleGroups.length} · Черновиков: {visibleDraftsCount}
      </p>

      {!visibleGroups.length ? (
        <div className="empty-page empty-inline">
          <FileText size={32} />
          <h3>{allGroups.length ? 'Ничего не найдено' : 'Пока нет черновиков'}</h3>
          <p>{allGroups.length
            ? 'Попробуйте изменить условия поиска.'
            : 'После анализа здесь появятся исходные объявления и готовые черновики.'}
          </p>
          <Button onClick={allGroups.length
            ? () => { setQuery(''); setCategory('all'); }
            : onNew}
          >
            {allGroups.length ? 'Сбросить фильтры' : 'Новый анализ'}
          </Button>
        </div>
      ) : (
        <div className="source-group-list">
          {visibleGroups.map(group => {
            const categoryIds = [...new Set(
              group.drafts.map(item => Number(item.mcId)).filter(Number.isFinite)
            )];

            return (
              <section className="source-group" key={group.key}>
                <div className="source-group-heading">
                  <span className="source-group-number">
                    {String(group.number).padStart(2, '0')}
                  </span>
                  <div className="source-group-heading-text">
                    <h2>Объявление {group.number}</h2>
                    {group.sourceId != null && (
                      <small>ID исходного объявления: {group.sourceId}</small>
                    )}
                  </div>
                  <span className="source-group-count">
                    {categoryIds.length} {pluralRu(categoryIds.length, 'категория', 'категории', 'категорий')}
                  </span>
                </div>

                <div className="source-group-original">
                  <span className="source-group-label">Исходное объявление</span>
                  <p>{group.description || 'Исходный текст не передан сервером.'}</p>
                </div>

                {categoryIds.length > 0 && (
                  <div className="source-group-categories" aria-label="Найденные категории">
                    {categoryIds.map(id => (
                      <span className="source-category-chip" key={id}>
                        {categoryFor(id)?.name || `Категория ${id}`}
                      </span>
                    ))}
                  </div>
                )}

                {group.drafts.length ? (
                  <div className="source-group-drafts">
                    {group.drafts.map(item => (
                      <article className="listing" key={item.id}>
                        <span className="draft-category">
                          {categoryFor(item.mcId)?.name || 'Категория не определена'}
                        </span>
                        <h3>{item.title || categoryFor(item.mcId)?.name || 'Без заголовка'}</h3>
                        <p className="listing-text">
                          {item.text || 'Описание пока не заполнено.'}
                        </p>
                        <div className="listing-actions">
                          <button type="button" onClick={() => onEdit(item)}>
                            <Pencil size={16} /> Редактировать
                          </button>
                          <button type="button" onClick={() => onCopy(item)}>
                            <Copy size={16} /> Скопировать
                          </button>
                          <button type="button" className="delete-link" onClick={() => onDelete(item)}>
                            <Trash2 size={16} /> Удалить
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="source-group-empty">
                    {group.hadGeneratedDrafts
                      ? 'Сохранённых черновиков для этого объявления нет.'
                      : 'Подходящих категорий для этого объявления не найдено.'}
                  </p>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}

function DeleteDraftModal({ target, count, pending, error, onClose, onConfirm }) {
  const isAll = target.type === 'all';
  const item = target.item;
  useEffect(() => {
    if (pending) return undefined;
    const closeOnEscape = event => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [pending, onClose]);

  return (
    <div
      className="modal-layer"
      onMouseDown={event => {
        if (!pending && event.target === event.currentTarget) onClose();
      }}
    >
      <section className="modal delete-draft-modal" role="dialog" aria-modal="true" aria-labelledby="delete-draft-title" aria-describedby="delete-draft-description">
        <div className="modal-head">
          <h2 id="delete-draft-title">{isAll ? 'Удалить все черновики?' : 'Удалить черновик?'}</h2>
        </div>
        <p id="delete-draft-description" className="delete-draft-description">
          {isAll
            ? `Все черновики (${count}), включая скрытые поиском и фильтрами, будут удалены без возможности восстановления.`
            : `Черновик «${item.title || categoryFor(item.mcId)?.name || 'Без заголовка'}» будет удалён без возможности восстановления.`}
        </p>
        {error && <p role="alert" className="inline-error">{error}</p>}
        <div className="modal-actions">
          <Button type="button" onClick={onClose} disabled={pending}>Отмена</Button>
          <Button type="button" className="button-danger" onClick={onConfirm} disabled={pending}>
            {pending ? 'Удаляем…' : isAll ? 'Удалить все' : 'Удалить'}
          </Button>
        </div>
      </section>
    </div>
  );
}

// Редактирование черновика
function EditModal({
  item,
  onClose,
  onSave,
}) {
  const [title, setTitle] = useState(item.title || '');
  const [text, setText] = useState(item.text || '');
  const [error, setError] = useState('');

  useEffect(() => {
    const listener = e => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', listener);

    return () => window.removeEventListener('keydown', listener);
  }, [onClose]);

  const submit = e => {
    e.preventDefault();

    if (!title.trim() || !text.trim()) {
      return setError(
        'Заполните заголовок и описание.'
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
        if (e.target === e.currentTarget) {
          onClose();
        }
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
              {categoryFor(item.mcId)?.name}
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
            />
          </label>

          <label className="field">
            <span>Описание</span>

            <textarea
              value={text}
              rows={7}
              onChange={e => setText(e.target.value)}
            />
          </label>

          {error && (
            <p className="inline-error">{error}</p>
          )}

          <div className="modal-actions">
            <Button
              type="button"
              onClick={onClose}
            >
              Отмена
            </Button>

            <Button
              type="submit"
              variant="primary"
            >
              <Check size={16} />
              Сохранить
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}

// Отображаем реальный ход обработки CSV, не выдумывая проценты выполнения запроса к ИИ.
function AnalysisOverlay({ progress }) {
  const { stage, completed, total } = progress;
  return (
    <div className="analysis-overlay">
      <section className="analysis-overlay-card" role="status" aria-live="polite" aria-atomic="true">
        <div className="analysis-loading-spinner" aria-hidden="true" />
        <h2>Идёт анализ объявлений</h2>
        <p className="analysis-loading-stage">{stage}</p>
        {total > 1 && (
          <div className="analysis-loading-progress">
            <div className="analysis-loading-progress-label">
              <span>Обработано объявлений</span>
              <strong>{completed} из {total}</strong>
            </div>
            <div className="analysis-loading-track">
              <span style={{ width: `${Math.round(completed / total * 100)}%` }} />
            </div>
          </div>
        )}
        <p className="analysis-loading-note">
          Приложение продолжает работать. Пожалуйста, дождитесь завершения обработки.
        </p>
      </section>
    </div>
  );
}

// Основное приложение
function App() {
  const [session, setSession] = useState({});
  const user = session?.user || null;
  const [page, setPage] = useState('overview');
  const [inputMode, setInputMode] = useState('text');

  const [description, setDescription] = useState('');

  const [records, setRecords] = useState([]);
  const [fileName, setFileName] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const sourceMetadataRef = useRef(new Map());

  const [drafts, setDrafts] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState({ stage: '', completed: 0, total: 1 });

  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [editItem, setEditItem] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  useEffect(() => {
    localStorage.removeItem('draftly-session-v1');
    window.history.replaceState(null, '', '/login');
  }, []);

  const onAuth = async (mode, credentials) => {
    const nextSession = await (mode === 'register'
      ? register(credentials)
      : login(credentials));
    window.history.replaceState(null, '', '/');
    setSession(nextSession);
    setError('');
  };

  const onLogout = async () => {
    const refreshToken = session?.refreshToken;
    window.history.replaceState(null, '', '/login');
    setSession({});
    sourceMetadataRef.current.clear();
    setAnalysis(null);
    setDrafts([]);
    go('overview');
    if (refreshToken) {
      try {
        await logout(refreshToken);
      } catch (err) {
        console.warn('Не удалось завершить сессию на сервере:', err);
      }
    }
  };

  useEffect(() => {
    if (!session?.accessToken) {
      setDrafts([]);
      return;
    }
    let active = true;
    listDrafts(null, session.accessToken)
      .then(items => {
        if (active) setDrafts(items.map(item => ({
          ...item,
          ...(sourceMetadataRef.current.get(String(item.id)) || {}),
        })));
      })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [session?.accessToken]);

  useEffect(() => {
    if (!toast) return undefined;

    const timer = setTimeout(
      () => setToast(''),
      3200
    );

    return () => clearTimeout(timer);
  }, [toast]);

  const go = target => {
    setPage(target);

    setError('');

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  };

  const notify = text => setToast(text);

  const onAnalyze = async () => {
    if (analyzing) return;
    setError('');

    const sourceRows = inputMode === 'text'
      ? [{ id: '1', description: description.trim() }]
      : records;

    if (!sourceRows.length || sourceRows.some(row => row.description.length < 12)) {
      setError('Введите описание не короче 12 символов или загрузите корректный CSV.');
      return;
    }

    const runId = crypto.randomUUID();
    const completedGroups = [];
    const sourceByDraftId = new Map();
    let oldDraftsDeleted = false;

    setAnalyzing(true);
    setAnalysisProgress({
      stage: 'Удаляем черновики предыдущего анализа…',
      completed: 0,
      total: sourceRows.length,
    });

    try {
      // Не начинаем новый анализ, пока сервер не подтвердил удаление старых черновиков.
      await deleteAllDrafts(session.accessToken);
      oldDraftsDeleted = true;
      setDrafts([]);
      setAnalysis(null);
      sourceMetadataRef.current.clear();

      for (const [index, row] of sourceRows.entries()) {
        setAnalysisProgress({
          stage: `Анализируем объявление ${index + 1} из ${sourceRows.length}…`,
          completed: index,
          total: sourceRows.length,
        });

        const result = await analyzeText(row.description, MAIN_CATEGORY_ID, session.accessToken);
        const sourceKey = `${runId}:${row.id}`;
        const proposals = (result.drafts || []).map(draft => ({ ...draft, key: draft.id }));

        proposals.forEach(draft => {
          if (draft.id != null) {
            sourceByDraftId.set(String(draft.id), {
              sourceKey,
              sourceId: row.id,
              sourceIndex: index + 1,
              sourceDescription: row.description,
            });
          }
        });

        completedGroups.push({
          id: row.id,
          sourceKey,
          description: row.description,
          proposals,
        });

        setAnalysisProgress({
          stage: `Объявление ${index + 1} обработано`,
          completed: index + 1,
          total: sourceRows.length,
        });
      }

      setAnalysisProgress({
        stage: 'Загружаем готовые черновики…',
        completed: sourceRows.length,
        total: sourceRows.length,
      });

      sourceMetadataRef.current = sourceByDraftId;
      const storedDrafts = await listDrafts(null, session.accessToken);
      const enrichedDrafts = storedDrafts.map(draft => ({
        ...draft,
        ...(sourceByDraftId.get(String(draft.id)) || {}),
      }));

      setDrafts(enrichedDrafts);
      setAnalysis({ runId, sourceType: inputMode, filename: fileName, groups: completedGroups });
      setPage('drafts');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      notify('Анализ завершён. Черновики готовы.');
    } catch (err) {
      // Если ошибка произошла посреди CSV, сохраним доступ к уже созданным черновикам.
      if (oldDraftsDeleted) {
        sourceMetadataRef.current = sourceByDraftId;
        setAnalysis({ runId, sourceType: inputMode, filename: fileName, groups: completedGroups });
        try {
          const storedDrafts = await listDrafts(null, session.accessToken);
          setDrafts(storedDrafts.map(draft => ({
            ...draft,
            ...(sourceByDraftId.get(String(draft.id)) || {}),
          })));
        } catch {
          // Покажем исходную ошибку анализа, не маскируя её ошибкой обновления списка.
        }
      }
      setError(err.message || 'Не удалось выполнить анализ.');
    } finally {
      setAnalyzing(false);
    }
  };

  const copy = async item => {
    try {
      await navigator.clipboard.writeText(
        `${item.title || ''}\n\n${item.text || ''}`
      );

      notify('Текст скопирован');
    } catch {
      notify('Не удалось скопировать текст');
    }
  };

  const deleteDraft = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    setDeleteError('');
    try {
      if (deleteTarget.type === 'all') {
        await deleteAllDrafts(session.accessToken);
        setDrafts([]);
        setAnalysis(null);
        sourceMetadataRef.current.clear();
        notify('Все черновики удалены');
      } else {
        await removeDraft(deleteTarget.item.id, session.accessToken);
        setDrafts(prev => prev.filter(d => d.id !== deleteTarget.item.id));
        notify('Черновик удалён');
      }
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(err.message || 'Не удалось удалить черновик.');
    } finally {
      setDeleting(false);
    }
  };

  const saveEdit = async item => {
    try {
      const updated = await updateDraft(item, session.accessToken);
      setDrafts(prev => prev.map(d => d.id === item.id ? { ...d, ...updated } : d));
      setEditItem(null);
      notify('Изменения сохранены');
    } catch (err) { setError(err.message); }
  };

  if (!user) {
    return <AuthPage onLogin={onAuth} connectionError={error} />;
  }

  return (
    <div className="app-shell">
      <AppHeader
        user={{ ...user, name: `${user.firstName} ${user.lastName}`.trim() }}
        page={page}
        draftsCount={drafts.length}
        go={go}
        onLogout={onLogout}
      />

      <main className="main-content" aria-busy={analyzing}>
        {page === 'overview' && (
          <OverviewPage
            inputMode={inputMode}
            setInputMode={setInputMode}
            description={description}
            setDescription={setDescription}
            records={records}
            setRecords={setRecords}
            fileName={fileName}
            setFileName={setFileName}
            onAnalyze={onAnalyze}
            error={error}
            analyzing={analyzing}
          />
        )}

        {page === 'drafts' && (
          <DraftsPage
            items={drafts}
            analysis={analysis}
            onNew={() => go('overview')}
            onEdit={setEditItem}
            onDelete={item => {
              setDeleteError('');
              setDeleteTarget({ type: 'one', item });
            }}
            onDeleteAll={() => {
              setDeleteError('');
              setDeleteTarget({ type: 'all' });
            }}
            onCopy={copy}
          />
        )}
      </main>

      {analyzing && <AnalysisOverlay progress={analysisProgress} />}

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
      {deleteTarget && (
        <DeleteDraftModal
          target={deleteTarget}
          count={drafts.length}
          pending={deleting}
          error={deleteError}
          onClose={() => setDeleteTarget(null)}
          onConfirm={deleteDraft}
        />
      )}
    </div>
  );
}

export default App;
