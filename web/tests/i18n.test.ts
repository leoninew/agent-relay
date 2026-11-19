import { describe, expect, it, vi } from "vitest";

import en from "@/i18n/en";
import zhCN from "@/i18n/zh-CN";
import { i18n, translateMessage } from "@/i18n";
import { formatDate, formatMinute, sameLocalDay } from "@/utils/time";

function entries(value: Record<string, unknown>, prefix = ""): Record<string, string[]> {
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, item]) => {
      const path = prefix ? `${prefix}.${key}` : key;
      if (typeof item === "string") {
        return [[path, [...item.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()]];
      }
      return Object.entries(entries(item as Record<string, unknown>, path));
    }),
  );
}

describe("translations", () => {
  it("groups equal instants and crosses midnight in local time with explicit-offset input", () => {
    const previous = new Date(2026, 10, 19, 23, 59).toISOString();
    const next = new Date(2026, 10, 20, 0, 1).toISOString();
    const nextWithOffset = `${new Date(Date.parse(next) + 8 * 60 * 60 * 1000).toISOString().slice(0, -1)}+08:00`;

    expect(formatMinute(previous)).toBe("23:59");
    expect(formatMinute(next)).toBe("00:01");
    expect(formatMinute(nextWithOffset)).toBe("00:01");
    expect(sameLocalDay(previous, next)).toBe(false);
    expect(sameLocalDay(next, nextWithOffset)).toBe(true);
  });
  it("has matching keys and interpolation parameters", () => {
    expect(entries(zhCN)).toEqual(entries(en));
  });

  it("renders existing descriptors and dates in the current language", () => {
    const descriptor = { key: "settings.loadFailed", requestId: "req1" };
    i18n.global.locale.value = "en";
    const english = translateMessage(descriptor);
    const englishDate = formatDate("2026-01-02T12:00:00");
    i18n.global.locale.value = "zh-CN";
    expect(translateMessage(descriptor)).not.toBe(english);
    expect(translateMessage(descriptor)).toContain("req1");
    expect(formatDate("2026-01-02T12:00:00")).not.toBe(englishDate);
    expect(sameLocalDay("2026-01-02T12:00:00", "2026-01-02T23:00:00")).toBe(true);
    i18n.global.locale.value = "en";
  });

  it("compiles every translation with its interpolation parameters", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      for (const [locale, dictionary] of [
        ["en", en],
        ["zh-CN", zhCN],
      ] as const) {
        i18n.global.locale.value = locale;
        for (const [key, parameters] of Object.entries(entries(dictionary))) {
          const values = Object.fromEntries(parameters.map((parameter) => [parameter, "value"]));
          expect(i18n.global.t(key, values)).not.toBe(key);
        }
      }
      expect(consoleError).not.toHaveBeenCalled();
      expect(consoleWarn).not.toHaveBeenCalled();
    } finally {
      i18n.global.locale.value = "en";
      consoleError.mockRestore();
      consoleWarn.mockRestore();
    }
  });
});
