export function booleanLabel(value, trueLabel = 'YES', falseLabel = 'NO') {
  if (value === true) return trueLabel;
  if (value === false) return falseLabel;
  return 'UNKNOWN';
}

export function valueOrUnknown(value) {
  return value === null || value === undefined || value === '' ? 'UNKNOWN' : value;
}

export function arrayCountOrUnknown(value) {
  return Array.isArray(value) ? value.length : 'UNKNOWN';
}
