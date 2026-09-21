import { describe, expect, it } from "vitest";

import { firstOwnImage, ownPostImage } from "./og-image";

const ORIGIN = "https://puppets.jp";
const media = (key: string) => ({ provider: "local", id: "m", meta: { storageKey: key } });

describe("ownPostImage", () => {
	it("featured_image を最優先 (動画があっても)", () => {
		expect(
			ownPostImage({ data: { featured_image: media("og.jpg"), video_url: "https://youtu.be/utfWl60tUoI" } }, ORIGIN),
		).toBe("https://puppets.jp/_emdash/api/media/file/og.jpg");
	});

	it("次に写真 (photos 先頭)", () => {
		expect(ownPostImage({ data: { photos: [media("p.jpg")] } }, ORIGIN)).toBe(
			"https://puppets.jp/_emdash/api/media/file/p.jpg",
		);
	});

	it("未保存の動画投稿は YouTube サムネイル", () => {
		expect(ownPostImage({ data: { video_url: "https://youtu.be/utfWl60tUoI" } }, ORIGIN)).toBe(
			"https://i.ytimg.com/vi/utfWl60tUoI/hqdefault.jpg",
		);
	});

	it("素材が無ければ null", () => {
		expect(ownPostImage({ data: {} }, ORIGIN)).toBeNull();
	});
});

describe("firstOwnImage", () => {
	it("素材を持つ最初の投稿", () => {
		expect(firstOwnImage([{ data: {} }, { data: { featured_image: media("a.jpg") } }], ORIGIN)).toBe(
			"https://puppets.jp/_emdash/api/media/file/a.jpg",
		);
	});
});
