import { describe, expect, it } from "vitest";

import { mediaUrl, toPhotos } from "./media";

describe("mediaUrl", () => {
	it("src があればそれを使う", () => {
		expect(mediaUrl({ src: "/_emdash/api/media/file/a.jpg" })).toBe("/_emdash/api/media/file/a.jpg");
	});
	it("seed で取り込んだローカル画像は storageKey から組み立てる", () => {
		expect(mediaUrl({ provider: "local", id: "x", meta: { storageKey: "01ABC.jpg" } })).toBe(
			"/_emdash/api/media/file/01ABC.jpg",
		);
	});
	it("解決できなければ null", () => {
		expect(mediaUrl(null)).toBeNull();
		expect(mediaUrl({ id: "x" })).toBeNull();
		expect(mediaUrl("str")).toBeNull();
	});
});

describe("toPhotos", () => {
	it("配列以外は空", () => {
		expect(toPhotos(undefined)).toEqual([]);
	});
	it("解決できない要素 (取り込み失敗の null 等) は捨てる", () => {
		expect(
			toPhotos([{ meta: { storageKey: "a.jpg" }, alt: "A", width: 10, height: 20 }, null]),
		).toEqual([{ url: "/_emdash/api/media/file/a.jpg", alt: "A", width: 10, height: 20 }]);
	});
});
