const MASK_CHAR = "*";
const EMAIL_EDGE_CHARS = 3;
const SHORT_EMAIL_EDGE_CHARS = 1;
const MIN_HIDDEN_EMAIL_CHARS = 6;
const PHONE_EDGE_DIGITS = 2;
const MIN_HIDDEN_PHONE_DIGITS = 3;
const EMAIL_PATTERN = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

export function maskEmail(email: string): string {
  const separatorIndex = email.lastIndexOf("@");
  if (separatorIndex <= 0) return email;
  const localPart = email.slice(0, separatorIndex);
  const domain = email.slice(separatorIndex);
  const isLongEnough = localPart.length >= EMAIL_EDGE_CHARS * 2 + 1;
  const edgeChars = isLongEnough ? EMAIL_EDGE_CHARS : SHORT_EMAIL_EDGE_CHARS;
  const head = localPart.slice(0, edgeChars);
  const tail = localPart.length > edgeChars * 2 ? localPart.slice(-edgeChars) : "";
  const hiddenCount = Math.max(MIN_HIDDEN_EMAIL_CHARS, localPart.length - head.length - tail.length);
  return `${head}${MASK_CHAR.repeat(hiddenCount)}${tail}${domain}`;
}

export function maskPhone(phone: string): string {
  const digitCount = phone.replace(/\D/g, "").length;
  const showsEdges = digitCount >= PHONE_EDGE_DIGITS * 2 + MIN_HIDDEN_PHONE_DIGITS;
  let digitIndex = 0;
  return phone.replace(/\d/g, (digit) => {
    const position = digitIndex++;
    const isEdge = position < PHONE_EDGE_DIGITS || position >= digitCount - PHONE_EDGE_DIGITS;
    return showsEdges && isEdge ? digit : MASK_CHAR;
  });
}

export function maskEmailsIn(text: string): string {
  return text.replace(EMAIL_PATTERN, maskEmail);
}

export function maskContact(value: string): string {
  return value.includes("@") ? maskEmail(value) : maskPhone(value);
}
