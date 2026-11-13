import { i18n } from "@/i18n";

function format(value: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(i18n.global.locale.value, options).format(new Date(value));
}

export function formatTime(value: string): string {
  return format(value, { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
}

export function formatMinute(value: string): string {
  return format(value, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}

export function formatDate(value: string): string {
  return format(value, { month: "long", day: "numeric", weekday: "long" });
}

export function formatDateTime(value: string): string {
  return format(value, {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
}

export function sameLocalDay(first: string, second: string): boolean {
  const left = new Date(first);
  const right = new Date(second);
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}
