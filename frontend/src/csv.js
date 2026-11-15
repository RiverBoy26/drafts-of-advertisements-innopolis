export const MAX_DESCRIPTION_LENGTH = 10000;

// CSV с запятой или точкой с запятой, кавычками и переносами строк в ячейках.
export function parseCsv(content) {
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
    if (currentRow.some(cell => cell.trim())) rows.push(currentRow);
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
      if (ch === '\r' && source[i + 1] === '\n') i++;
      finishRow();
    } else {
      value += ch;
    }
  }

  if (quoted) throw new Error('В CSV есть незакрытые кавычки.');
  if (value || currentRow.length) finishRow();
  if (rows.length < 2) {
    throw new Error('CSV должен содержать заголовки и хотя бы одну строку данных.');
  }

  const headers = rows[0].map(v => v.trim().toLowerCase());
  const idIndex = headers.findIndex(h => ['id', 'testcase', 'ид'].includes(h));
  const descriptionIndex = headers.findIndex(h =>
    ['description', 'описание', 'text', 'текст'].includes(h)
  );
  if (idIndex < 0 || descriptionIndex < 0) {
    throw new Error('В CSV нужны столбцы id или testcase и description.');
  }

  const seenIds = new Set();
  return rows.slice(1).map((cols, index) => {
    const id = (cols[idIndex] || '').trim();
    const description = (cols[descriptionIndex] || '').trim();
    if (!id || !description) {
      throw new Error(`В строке ${index + 2} не заполнен id или description.`);
    }
    if (seenIds.has(id)) throw new Error(`Повторяется id «${id}».`);
    seenIds.add(id);
    return { id, description };
  });
}
