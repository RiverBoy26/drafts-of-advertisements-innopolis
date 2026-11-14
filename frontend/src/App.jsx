
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronDown, CircleHelp,
  Copy, FileSpreadsheet, FileText, House, LogOut, Menu, PanelLeftClose,
  Pencil, Search, ShieldCheck, Sparkles, Trash2, UploadCloud, UserRound,
  X, AlertCircle, Eye, EyeOff, SlidersHorizontal, Clock3, Plus,
} from 'lucide-react';

// Пока используется демонстрационный ответ. Backend позже вернёт
// микрокатегорию (mcId) и текст подготовленного объявления.
const MICROCATEGORIES = [
  { mcId: 101, name: 'Ремонт под ключ' },
  { mcId: 102, name: 'Штукатурные работы' },
  { mcId: 103, name: 'Плиточные работы' },
  { mcId: 104, name: 'Сантехника' },
  { mcId: 105, name: 'Электрика' },
  { mcId: 106, name: 'Поклейка обоев и малярные работы' },
];

const MAIN_CATEGORY_ID = 101;
const STORAGE = 'draftly-case-2026-v1';
const LEGACY_STORAGE = 'draftly-v1';

const categoryFor = id =>
  MICROCATEGORIES.find(c => c.mcId === Number(id));

function safeRead(key) {
  try {
    return JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return {};
  }
}

const initial = safeRead(STORAGE);
const previous = safeRead(LEGACY_STORAGE);

// Это именно примеры для проверки интерфейса,
// а не результат анализа введённого текста.

const DEMO_OUTPUT = [
  {
    mcId: 102,
    title: 'Штукатурные работы',
    text: 'Подготовка поверхностей и штукатурка стен перед чистовой отделкой.',
  },
  {
    mcId: 103,
    title: 'Укладка плитки',
    text: 'Облицовка поверхностей керамической плиткой и затирка межплиточных швов.',
  },
  {
    mcId: 104,
    title: 'Сантехнические работы',
    text: 'Установка раковин и смесителей, монтаж и замена сантехнических труб.',
  },
  {
    mcId: 105,
    title: 'Электромонтажные работы',
    text: 'Установка розеток и выключателей, монтаж электропроводки.',
  },
  {
    mcId: 106,
    title: 'Малярные работы и поклейка обоев',
    text: 'Покраска стен и потолков, подготовка поверхностей и поклейка обоев.',
  },
];

const DEMO_COUNTS = [2, 3, 4, 2, 5, 3, 2, 4];

function makeDemoAnalysis(rows, sourceType, filename) {
  const runId = crypto.randomUUID();

  return {
    runId,
    sourceType,
    filename,
    sourceMcId: MAIN_CATEGORY_ID,
    groups: rows.map((row, rowIndex) => {
      const count = DEMO_COUNTS[rowIndex % DEMO_COUNTS.length];
      const offset = (rowIndex * 2) % DEMO_OUTPUT.length;

      const proposals = Array.from({ length: count }, (_, idx) => {
        const template = DEMO_OUTPUT[
          (offset + idx) % DEMO_OUTPUT.length
        ];

        return {
          ...template,
          key: `${runId}:${rowIndex}:${template.mcId}`,
        };
      });

      return {
        id: row.id,
        description: row.description,
        proposals,
      };
    }),
  };
}

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
              Подготовленные тексты можно проверить и изменить в черновиках.
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
    <>
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
              inputMode === 'text'
                ? description.trim().length < 12
                : records.length === 0
            }
          >
            <Sparkles size={19} />
            Анализировать
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
    </>
  );
}

// Результаты анализа в разделе «Обзор»

function ResultPage({ analysis, onBack, onDrafts, onCopy }) {
  const total = analysis.groups.reduce(
    (sum, group) => sum + group.proposals.length,
    0
  );

  const isBatch = analysis.sourceType === 'csv';

  const renderProposal = (proposal, number) => (
    <article className="result-draft-row" key={proposal.key}>
      <span className="result-draft-index" aria-hidden="true">
        {String(number).padStart(2, '0')}
      </span>

      <div className="result-draft-body">
        <span className="draft-category">
          {categoryFor(proposal.mcId)?.name || 'Категория'}
        </span>
        <h3>{proposal.title}</h3>
        <p>{proposal.text}</p>
      </div>

      <button
        type="button"
        className="draft-copy"
        onClick={() => onCopy(proposal)}
        title="Скопировать текст объявления"
      >
        <Copy size={16} />
        <span>Копировать</span>
      </button>
    </article>
  );

  return (
    <>
      <div className="page-heading result-page-heading">
        <button
          className="back-link"
          type="button"
          onClick={onBack}
        >
          <ArrowLeft size={17} />
          К вводу данных
        </button>
        <h1>Результаты анализа</h1>
      </div>

      <div className="result-dashboard">
        <div className="result-success">
          <span className="result-success-icon">
            <CheckCircle2 size={24} />
          </span>

          <div>
            <strong>Черновики созданы</strong>
            <p>
              Все предложения автоматически добавлены
              в раздел «Черновики».
            </p>
          </div>
        </div>

        <div className="result-stat">
          <span>Обработано объявлений</span>
          <strong>{analysis.groups.length}</strong>
        </div>

        <div className="result-stat result-stat-accent">
          <span>Создано черновиков</span>
          <strong>{total}</strong>
        </div>
      </div>

      <div className="result-actions">
        <div>
          <h2>Готовые черновики</h2>
          <p>
            {isBatch
              ? 'По исходным объявлениям'
              : 'Для вашего объявления'}
          </p>
        </div>

        <Button
          variant="primary"
          type="button"
          onClick={onDrafts}
        >
          <FileText size={17} />
          Открыть черновики
          <ArrowRight size={16} />
        </Button>
      </div>

      <div className="analysis-group-list">
        {analysis.groups.map((group, index) => (
          isBatch ? (
            <details
              className="analysis-group"
              key={`${analysis.runId}-${index}`}
              open={index === 0 ? true : undefined}
            >
              <summary className="analysis-group-summary">
                <span className="analysis-group-title">
                  <span className="analysis-group-number">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <strong>Объявление {index + 1}</strong>
                </span>

                <span className="analysis-group-right">
                  <span className="analysis-group-count">
                    {group.proposals.length}{' '}
                    {group.proposals.length % 10 === 1 && group.proposals.length % 100 !== 11
                      ? 'черновик'
                      : group.proposals.length % 10 >= 2 && group.proposals.length % 10 <= 4 && (group.proposals.length % 100 < 12 || group.proposals.length % 100 > 14)
                        ? 'черновика'
                        : 'черновиков'}
                  </span>

                  <ChevronDown
                    size={19}
                    className="analysis-chevron"
                  />
                </span>
              </summary>

              <div className="analysis-group-body">
                {group.proposals.map((proposal, proposalIndex) =>
                  renderProposal(proposal, proposalIndex + 1)
                )}
              </div>
            </details>
          ) : (
            <div
              className="analysis-group analysis-group-single"
              key={`${analysis.runId}-${index}`}
            >
              {group.proposals.map((proposal, proposalIndex) =>
                renderProposal(proposal, proposalIndex + 1)
              )}
            </div>
          )
        ))}
      </div>
    </>
  );
}


// Страница «Черновики»
function DraftsPage({
  items,
  onNew,
  onEdit,
  onDelete,
  onCopy,
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState('newest');

  const filtered = useMemo(() => {
    return items
      .filter(item => {
        const haystack = `${
          item.title || ''
        } ${
          item.text || ''
        } ${
          categoryFor(item.mcId)?.name || ''
        } ${
          item.sourceId || ''
        }`.toLowerCase();

        return (
          haystack.includes(query.toLowerCase()) &&
          (
            category === 'all' ||
            Number(category) === Number(item.mcId)
          )
        );
      })
      .sort((a, b) => {
        const first = new Date(
          a.updatedAt || a.createdAt
        ).getTime();

        const second = new Date(
          b.updatedAt || b.createdAt
        ).getTime();

        return sort === 'newest'
          ? second - first
          : first - second;
      });
  }, [items, query, category, sort, categories]);

  return (
    <>
      <div className="page-heading">
        <h1>Черновики</h1>
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
            <button
              aria-label="Очистить"
              onClick={() => setQuery('')}
            >
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
              <option key={c.mcId} value={c.mcId}>
                {c.name}
              </option>
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
              : 'Пока нет черновиков'}
          </h3>

          <p>
            {items.length
              ? 'Попробуйте изменить условия поиска.'
              : 'После анализа здесь появятся сохранённые объявления.'}
          </p>

          <Button
            onClick={
              items.length
                ? () => {
                    setQuery('');
                    setCategory('all');
                  }
                : onNew
            }
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

              {/* Название объявления */}
              <h3>
                {item.title ||
                  categoryFor(item.mcId)?.name ||
                  'Без заголовка'}
              </h3>

              {/* Категория */}
              <p className="listing-category">
                Категория: {categoryFor(item.mcId)?.name || 'Не определена'}
              </p>

              {/* Описание */}
              <p className="listing-text">
                {item.text || 'Описание пока не заполнено.'}
              </p>

              {/* Кнопки управления */}
              <div className="listing-actions">
                <button onClick={() => onEdit(item)}>
                  <Pencil size={16} />
                  Редактировать
                </button>

                <button onClick={() => onCopy(item)}>
                  <Copy size={16} />
                  Скопировать
                </button>

                <button
                  className="delete-link"
                  onClick={() => onDelete(item)}
                >
                  <Trash2 size={16} />
                  Удалить
                </button>
              </div>

            </article>
          ))}
        </div>

      )}
    </>
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

// Основное приложение
function App() {
  const [session, setSession] = useState(() => safeRead(SESSION_STORAGE));
  const sessionRef = useRef(session);
  const user = session?.user || null;
  const [categories, setCategories] = useState([]);
  const [page, setPage] = useState('overview');
  const [inputMode, setInputMode] = useState('text');

  const [description, setDescription] = useState(
    initial.description || ''
  );

  const [records, setRecords] = useState([]);
  const [fileName, setFileName] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [analysis, setAnalysis] = useState(null);

  // Старые объявления не теряются.
  // Теперь они также считаются черновиками.
  const [drafts, setDrafts] = useState(() => {
    const saved = [
      ...(initial.drafts || []),
      ...(initial.ads || []),
    ];

    return [
      ...new Map(
        saved.map(item => [item.id, item])
      ).values(),
    ];
  });

  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [editItem, setEditItem] = useState(null);

  useEffect(() => {
    localStorage.setItem(
      STORAGE,
      JSON.stringify({
        user,
        description,
        drafts,
        ads: [],
      })
    );
  }, [user, description, drafts]);

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

    if (target === 'overview') {
      setShowResults(false);
    }

    setError('');

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  };

  const notify = text => setToast(text);

  // Демонстрационный анализ и автоматическое создание черновиков.
  const onAnalyze = () => {
    setError('');

    const sourceRows = inputMode === 'text'
      ? [{ id: '1', description: description.trim() }]
      : records;

    if (
      !sourceRows.length ||
      sourceRows.some(row => row.description.length < 12)
    ) {
      setError(
        'Введите описание не короче 12 символов или загрузите корректный CSV.'
      );
      return;
    }
  };

    const nextAnalysis = makeDemoAnalysis(sourceRows, inputMode, fileName);
    const createdAt = new Date().toISOString();

    const newDrafts = nextAnalysis.groups.flatMap(group =>
      group.proposals.map(proposal => ({
        id: crypto.randomUUID(),
        proposalKey: proposal.key,
        analysisId: nextAnalysis.runId,
        sourceId: inputMode === 'csv' ? group.id : null,
        mcId: proposal.mcId,
        title: proposal.title,
        text: proposal.text,
        createdAt,
      }))
    );

    setAnalysis(nextAnalysis);
    setDrafts(prev => {
      const updated = [...newDrafts, ...prev];
      // Сохраняем сразу, чтобы черновики не пропали после обновления страницы.
      try {
        localStorage.setItem(STORAGE, JSON.stringify({
          user, description, drafts: updated, ads: [],
        }));
      } catch (e) {
        console.warn('Не удалось сохранить черновики в браузере:', e);
      }
      return updated;
    });
    setShowResults(true);

    window.scrollTo({ top: 0, behavior: 'smooth' });
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

  const deleteDraft = item => {
    if (!window.confirm('Удалить черновик?')) {
      return;
    }

    setDrafts(prev =>
      prev.filter(d => d.id !== item.id)
    );

    notify('Черновик удалён');
  };

  const saveEdit = item => {
    setDrafts(prev =>
      prev.map(d =>
        d.id === item.id ? item : d
      )
    );

    setEditItem(null);
    notify('Изменения сохранены');
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
        onLogout={() => {
          setUser(null);
          go('overview');
        }}
      />

      <main className="main-content">
        {page === 'overview' && !showResults && (
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
          />
        )}

        {page === 'overview' && showResults && analysis && (
          <ResultPage
            analysis={analysis}
            onBack={() => setShowResults(false)}
            onDrafts={() => go('drafts')}
            onCopy={copy}
          />
        )}

        {page === 'drafts' && (
          <DraftsPage
            items={drafts}
            onNew={() => go('overview')}
            onEdit={setEditItem}
            onDelete={deleteDraft}
            onCopy={copy}
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