/**
 * コンテンツ自身から OGP 画像を得る。
 * 投稿に動画・写真が無い場合、本文中のリンク先 (Spotify / Apple Music / YouTube / 一般サイトの og:image) の画像を使う
 */
import { mediaUrl } from "./media";
import { youtubeId, youtubeThumbnail } from "./youtube";

const FETCH_TIMEOUT_MS = 3000;
const MAX_HTML_BYTES = 256 * 1024;

// 同一 isolate 内のメモ (Workers の isolate は複数リクエストで再利用される)
const memo = new Map<string, Promise<string | null>>();

type Fetcher = (input: string, init?: RequestInit) => Promise<Response>;

/** HTML から og:image / twitter:image を取り出す (属性順は問わない) */
export function extractOgImage(html: string, baseUrl: string): string | null {
	for (const tag of html.match(/<meta\b[^>]*>/gi) ?? []) {
		const key = /\b(?:property|name)\s*=\s*["']([^"']+)["']/i.exec(tag)?.[1]?.toLowerCase();
		if (key !== "og:image" && key !== "og:image:secure_url" && key !== "twitter:image") continue;
		const content = /\bcontent\s*=\s*["']([^"']+)["']/i.exec(tag)?.[1];
		if (!content) continue;
		try {
			return new URL(content.replace(/&amp;/g, "&"), baseUrl).href;
		} catch {
			continue;
		}
	}
	return null;
}

/** Apple Music の URL からアイテム ID (曲なら ?i=、それ以外はパス末尾の数字) */
export function appleMusicId(url: string): string | null {
	try {
		const u = new URL(url);
		if (!/(^|\.)music\.apple\.com$/.test(u.hostname)) return null;
		return u.searchParams.get("i") ?? /\/(\d+)\/?$/.exec(u.pathname)?.[1] ?? null;
	} catch {
		return null;
	}
}

async function fetchWithTimeout(fetcher: Fetcher, url: string, init: RequestInit = {}): Promise<Response> {
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
	try {
		// Cloudflare のエッジキャッシュに 1 日載せる (Workers 以外では無視される)
		return await fetcher(url, {
			...init,
			signal: controller.signal,
			redirect: "follow",
			cf: { cacheTtl: 86400, cacheEverything: true },
		} as RequestInit);
	} finally {
		clearTimeout(timer);
	}
}

async function resolve(url: string, fetcher: Fetcher): Promise<string | null> {
	const yt = youtubeId(url);
	if (yt) return youtubeThumbnail(yt);

	if (/^https:\/\/open\.spotify\.com\//.test(url)) {
		const res = await fetchWithTimeout(fetcher, `https://open.spotify.com/oembed?url=${encodeURIComponent(url)}`);
		if (!res.ok) return null;
		const json = (await res.json()) as { thumbnail_url?: string };
		return json.thumbnail_url ?? null;
	}

	const appleId = appleMusicId(url);
	if (appleId) {
		const res = await fetchWithTimeout(fetcher, `https://itunes.apple.com/lookup?id=${appleId}&country=jp`);
		if (!res.ok) return null;
		const json = (await res.json()) as { results?: { artworkUrl100?: string }[] };
		const art = json.results?.find((r) => r.artworkUrl100)?.artworkUrl100;
		return art ? art.replace(/\/\d+x\d+bb\./, "/1200x1200bb.") : null;
	}

	const res = await fetchWithTimeout(fetcher, url, {
		headers: { "User-Agent": "Mozilla/5.0 (compatible; puppets.jp OGP fetcher)", Accept: "text/html" },
	});
	if (!res.ok || !(res.headers.get("content-type") ?? "").includes("html")) return null;
	const html = (await res.text()).slice(0, MAX_HTML_BYTES);
	return extractOgImage(html, res.url || url);
}

/** 1 つの URL から画像を得る。失敗・タイムアウトは null */
export function ogImageForUrl(url: string, fetcher: Fetcher = fetch): Promise<string | null> {
	let pending = memo.get(url);
	if (!pending) {
		pending = resolve(url, fetcher).catch(() => null);
		memo.set(url, pending);
	}
	return pending;
}

interface PtBlock {
	_type: string;
	url?: unknown;
	markDefs?: { _type?: string; href?: unknown }[];
}

/** 本文 (Portable Text) に出てくる外部リンクを出現順に列挙する (自サイト・ライセンス表記は除く) */
export function contentLinks(blocks: unknown, siteOrigin: string): string[] {
	if (!Array.isArray(blocks)) return [];
	const urls: string[] = [];
	for (const block of blocks as PtBlock[]) {
		if (block._type === "embed" && typeof block.url === "string") urls.push(block.url);
		for (const def of block.markDefs ?? []) {
			if (def._type === "link" && typeof def.href === "string") urls.push(def.href);
		}
	}
	return [...new Set(urls)].filter((u) => {
		try {
			const { origin, hostname } = new URL(u);
			return origin !== siteOrigin && hostname !== "creativecommons.org" && /^https?:/.test(u);
		} catch {
			return false;
		}
	});
}

/** 本文のリンク先を先頭から最大 limit 件試し、最初に得られた画像を返す */
export async function firstLinkedImage(
	links: string[],
	fetcher: Fetcher = fetch,
	limit = 3,
): Promise<string | null> {
	for (const url of links.slice(0, limit)) {
		const image = await ogImageForUrl(url, fetcher);
		if (image) return image;
	}
	return null;
}

interface PostLike {
	data: { video_url?: string | null; featured_image?: unknown; photos?: unknown; content?: unknown };
}

/** 投稿自身の素材 (動画サムネイル → 写真) から OGP 画像を得る。無ければ null */
export function ownPostImage(post: PostLike, origin: string): string | null {
	const vid = youtubeId(post.data.video_url);
	if (vid) return youtubeThumbnail(vid);
	const photos = Array.isArray(post.data.photos) ? post.data.photos : [];
	const url = mediaUrl(post.data.featured_image) ?? mediaUrl(photos[0]);
	return url ? new URL(url, origin).href : null;
}

/** 投稿の OGP 画像: 自身の素材 → 本文リンク先の画像 */
export async function postOgImage(post: PostLike, origin: string, fetcher: Fetcher = fetch): Promise<string | null> {
	return ownPostImage(post, origin) ?? firstLinkedImage(contentLinks(post.data.content, origin), fetcher);
}

/** 投稿リストの先頭から、自身の素材を持つ最初の投稿の画像 (一覧・タグ・アーティストページ用) */
export function firstOwnImage(posts: PostLike[], origin: string): string | null {
	for (const post of posts) {
		const image = ownPostImage(post, origin);
		if (image) return image;
	}
	return null;
}
