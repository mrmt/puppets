import { describe, expect, it } from "vitest";

import { linkParagraphsToEmbeds, toEmbed } from "./embed";

describe("toEmbed", () => {
	it("Spotify 共有 URL (intl パス・クエリ付き)", () => {
		expect(toEmbed("https://open.spotify.com/intl-ja/album/4mAWMc8dq25WvSrpyvaLCm?si=x")).toEqual({
			kind: "player",
			src: "https://open.spotify.com/embed/album/4mAWMc8dq25WvSrpyvaLCm",
			height: 352,
		});
	});

	it("Spotify embed URL はそのまま正規化", () => {
		expect(toEmbed("https://open.spotify.com/embed/album/4hyRtPapIfbCLESVWL5RKC?utm_source=generator")?.src).toBe(
			"https://open.spotify.com/embed/album/4hyRtPapIfbCLESVWL5RKC",
		);
	});

	it("Spotify トラックは低いプレイヤー", () => {
		expect(toEmbed("https://open.spotify.com/track/abc123")?.height).toBe(152);
	});

	it("Apple Music 共有 URL と embed URL", () => {
		expect(toEmbed("https://music.apple.com/jp/album/the-diastereomer-live-vocal-mix/1814540901")).toEqual({
			kind: "player",
			src: "https://embed.music.apple.com/jp/album/the-diastereomer-live-vocal-mix/1814540901",
			height: 450,
		});
		expect(toEmbed("https://embed.music.apple.com/jp/album/primrose-single/6786170308")?.src).toBe(
			"https://embed.music.apple.com/jp/album/primrose-single/6786170308",
		);
	});

	it("YouTube は nocookie の動画", () => {
		expect(toEmbed("https://youtu.be/utfWl60tUoI")).toEqual({
			kind: "video",
			src: "https://www.youtube-nocookie.com/embed/utfWl60tUoI",
		});
	});

	it("対応外は null", () => {
		expect(toEmbed("https://puppets.jp/fa")).toBeNull();
		expect(toEmbed("https://music.apple.com/jp/artist/sect-commune/486130726")).toBeNull();
		expect(toEmbed(undefined)).toBeNull();
	});
});

describe("linkParagraphsToEmbeds", () => {
	const para = (text: string, href?: string, extra: string[] = []) => ({
		_type: "block",
		_key: "b",
		markDefs: href ? [{ _type: "link", _key: "l", href }] : [],
		children: [{ _type: "span", text, marks: href ? ["l"] : [] }, ...extra.map((t) => ({ _type: "span", text: t, marks: [] }))],
	});

	it("埋め込み可能なリンクだけの段落は embed に", () => {
		const url = "https://open.spotify.com/intl-ja/album/4mAWMc8dq25WvSrpyvaLCm";
		expect(linkParagraphsToEmbeds([para("The Diastereomer", url)])).toEqual([{ _type: "embed", _key: "b", url }]);
	});

	it("前後に空白だけのスパンがあっても変換する", () => {
		const url = "https://music.apple.com/jp/album/x/1";
		expect(linkParagraphsToEmbeds([para("x", url, [" "])])[0]._type).toBe("embed");
	});

	it("文中のリンク・対応外リンク・リンク無しは変換しない", () => {
		const blocks = [
			para("Go listen", "https://open.spotify.com/album/abc", ["on Spotify"]),
			para("puppets", "https://puppets.jp/fa"),
			para("plain"),
			{ _type: "image", _key: "i" },
		];
		expect(linkParagraphsToEmbeds(blocks)).toEqual(blocks);
	});
});
