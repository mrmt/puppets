import { describe, expect, it } from "vitest";

import { formatDate } from "./format";

describe("formatDate", () => {
	it("日本時間の日付で YYYY.MM.DD", () => {
		// UTC 14:00 = JST 23:00 (同日)
		expect(formatDate(new Date("2026-09-09T14:00:00Z"))).toBe("2026.09.09");
		// UTC 23:28 = JST 翌日 08:28
		expect(formatDate(new Date("2026-07-25T23:28:56Z"))).toBe("2026.07.26");
	});
});
