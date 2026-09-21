import { describe, expect, it } from "vitest";

import { resolveLegacyPath, tagSlug } from "./legacy";
import tumblrIdMap from "./tumblr-id-map.json";

describe("resolveLegacyPath", () => {
	it("全 Tumblr 投稿 ID が新 slug に解決される (slug 部分の有無を問わない)", () => {
		for (const [id, slug] of Object.entries(tumblrIdMap as Record<string, string>)) {
			expect(resolveLegacyPath(`/post/${id}`)).toBe(`/posts/${slug}`);
			expect(resolveLegacyPath(`/post/${id}/old-tumblr-slug`)).toBe(`/posts/${slug}`);
		}
	});

	it("日本語 slug を含むパーセントエンコード URL", () => {
		expect(
			resolveLegacyPath(
				"/post/821889724426977280/diastereomer35%E5%B9%B4%E4%BB%A5%E4%B8%8A%E3%81%B6%E3%82%8A",
			),
		).toBe("/posts/diastereomer-35-primrose");
	});

	it("未知の投稿 ID は null", () => {
		expect(resolveLegacyPath("/post/1")).toBeNull();
	});

	it("アーティストタグはアーティストページへ", () => {
		expect(resolveLegacyPath("/tagged/sectcommune")).toBe("/artists/sect-commune");
		expect(resolveLegacyPath("/tagged/the%20twilight%20states")).toBe("/artists/the-twilight-states");
		expect(resolveLegacyPath("/tagged/dizzy+states")).toBe("/artists/dizzy-states");
		expect(resolveLegacyPath("/tagged/metafictions/page/2")).toBe("/artists/metafictions");
	});

	it("その他のタグはタグページへ", () => {
		expect(resolveLegacyPath("/tagged/live")).toBe("/tag/live");
		expect(resolveLegacyPath("/tagged/alpha-beta")).toBe("/tag/alpha-beta");
	});

	it("RSS・アーカイブ・ページング", () => {
		expect(resolveLegacyPath("/rss")).toBe("/rss.xml");
		expect(resolveLegacyPath("/archive")).toBe("/posts");
		expect(resolveLegacyPath("/archive/2025/3")).toBe("/posts");
		expect(resolveLegacyPath("/page/2")).toBe("/posts?page=2");
		expect(resolveLegacyPath("/page/1")).toBe("/posts");
	});

	it("該当しないパスは null", () => {
		expect(resolveLegacyPath("/")).toBeNull();
		expect(resolveLegacyPath("/posts/foo")).toBeNull();
	});
});

describe("tagSlug", () => {
	it("seed 側 (python-slugify) と同じ規則", () => {
		expect(tagSlug("the twilight states")).toBe("the-twilight-states");
		expect(tagSlug("Alpha-Beta")).toBe("alpha-beta");
	});
});

describe("seed とのタグ slug 整合", () => {
	it("seed の全タグで tagSlug(label) === slug", async () => {
		const seed = (await import("../../seed/seed.json")).default as {
			taxonomies: { terms: { slug: string; label: string }[] }[];
		};
		for (const term of seed.taxonomies[0].terms) {
			expect(tagSlug(term.label)).toBe(term.slug);
		}
	});
});
