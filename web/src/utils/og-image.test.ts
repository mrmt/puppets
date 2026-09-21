import { describe, expect, it } from "vitest";

import { appleMusicId, contentLinks, extractOgImage, firstOwnImage, ogImageForUrl, ownPostImage, postOgImage } from "./og-image";

const ORIGIN = "https://puppets.jp";

/** URL ごとに応答を返すテスト用 fetch */
function fakeFetch(routes: Record<string, () => Response>) {
	const calls: string[] = [];
	const fetcher = async (url: string) => {
		calls.push(url);
		const route = routes[url];
		if (!route) return new Response("not found", { status: 404 });
		const res = route();
		Object.defineProperty(res, "url", { value: url });
		return res;
	};
	return { fetcher, calls };
}

const html = (body: string) => () => new Response(body, { headers: { "content-type": "text/html; charset=utf-8" } });
const json = (body: unknown) => () => Response.json(body);

describe("extractOgImage", () => {
	it("property / content の順不同、相対 URL は絶対化", () => {
		expect(extractOgImage('<meta content="/a.jpg" property="og:image">', "https://ex.com/p")).toBe("https://ex.com/a.jpg");
		expect(extractOgImage('<meta name="twitter:image" content="https://cdn/x.png">', "https://ex.com")).toBe("https://cdn/x.png");
	});
	it("無ければ null", () => {
		expect(extractOgImage("<meta name=description content=x>", "https://ex.com")).toBeNull();
	});
});

describe("appleMusicId", () => {
	it("アルバムはパス末尾、曲は ?i=", () => {
		expect(appleMusicId("https://music.apple.com/jp/album/the-diastereomer-live-vocal-mix/1814540901")).toBe("1814540901");
		expect(appleMusicId("https://music.apple.com/jp/album/x/1?i=222")).toBe("222");
		expect(appleMusicId("https://example.com/1")).toBeNull();
	});
});

describe("contentLinks", () => {
	it("embed と link を出現順に、自サイトと CC ライセンスを除いて列挙", () => {
		const blocks = [
			{ _type: "embed", url: "https://open.spotify.com/album/a" },
			{
				_type: "block",
				markDefs: [
					{ _type: "link", href: "https://puppets.jp/fa" },
					{ _type: "link", href: "https://creativecommons.org/licenses/by/2.0/" },
					{ _type: "link", href: "https://bandcamp.example/track" },
					{ _type: "link", href: "https://open.spotify.com/album/a" },
				],
			},
		];
		expect(contentLinks(blocks, ORIGIN)).toEqual(["https://open.spotify.com/album/a", "https://bandcamp.example/track"]);
	});
});

describe("ownPostImage / firstOwnImage", () => {
	it("動画サムネイル → 写真の順、写真は絶対 URL", () => {
		expect(ownPostImage({ data: { video_url: "https://youtu.be/utfWl60tUoI" } }, ORIGIN)).toBe(
			"https://i.ytimg.com/vi/utfWl60tUoI/hqdefault.jpg",
		);
		expect(ownPostImage({ data: { photos: [{ meta: { storageKey: "a.jpg" } }] } }, ORIGIN)).toBe(
			"https://puppets.jp/_emdash/api/media/file/a.jpg",
		);
		expect(ownPostImage({ data: {} }, ORIGIN)).toBeNull();
	});
	it("一覧は素材を持つ最初の投稿", () => {
		expect(firstOwnImage([{ data: {} }, { data: { video_url: "https://youtu.be/utfWl60tUoI" } }], ORIGIN)).toContain("utfWl60tUoI");
	});
});

describe("postOgImage (本文リンク先から取得)", () => {
	const content = (href: string) => [{ _type: "block", markDefs: [{ _type: "link", href }] }];

	it("Spotify は oEmbed のサムネイル", async () => {
		const url = "https://open.spotify.com/intl-ja/album/sp1";
		const { fetcher } = fakeFetch({
			[`https://open.spotify.com/oembed?url=${encodeURIComponent(url)}`]: json({ thumbnail_url: "https://i.scdn.co/sp1.jpg" }),
		});
		expect(await postOgImage({ data: { content: content(url) } }, ORIGIN, fetcher)).toBe("https://i.scdn.co/sp1.jpg");
	});

	it("Apple Music は iTunes lookup のアートワークを 1200px に", async () => {
		const url = "https://music.apple.com/jp/album/x/900001";
		const { fetcher } = fakeFetch({
			"https://itunes.apple.com/lookup?id=900001&country=jp": json({
				results: [{ artworkUrl100: "https://is1.mzstatic.com/a/100x100bb.jpg" }],
			}),
		});
		expect(await postOgImage({ data: { content: content(url) } }, ORIGIN, fetcher)).toBe(
			"https://is1.mzstatic.com/a/1200x1200bb.jpg",
		);
	});

	it("一般サイトは og:image、失敗したリンクは飛ばして次を試す", async () => {
		const { fetcher, calls } = fakeFetch({
			"https://site.example/ok": html('<meta property="og:image" content="https://site.example/og.jpg">'),
		});
		const blocks = [
			{
				_type: "block",
				markDefs: [
					{ _type: "link", href: "https://dead.example/404" },
					{ _type: "link", href: "https://site.example/ok" },
				],
			},
		];
		expect(await postOgImage({ data: { content: blocks } }, ORIGIN, fetcher)).toBe("https://site.example/og.jpg");
		expect(calls).toEqual(["https://dead.example/404", "https://site.example/ok"]);
	});

	it("自身の素材があればリンク先は取得しない", async () => {
		const { fetcher, calls } = fakeFetch({});
		await postOgImage({ data: { video_url: "https://youtu.be/utfWl60tUoI", content: content("https://site.example/x") } }, ORIGIN, fetcher);
		expect(calls).toEqual([]);
	});

	it("同じ URL は 2 回目以降メモから返す", async () => {
		const { fetcher, calls } = fakeFetch({
			"https://memo.example/p": html('<meta property="og:image" content="https://memo.example/i.jpg">'),
		});
		await ogImageForUrl("https://memo.example/p", fetcher);
		await ogImageForUrl("https://memo.example/p", fetcher);
		expect(calls).toHaveLength(1);
	});
});
