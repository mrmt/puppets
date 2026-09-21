import tumblrIdMap from "./tumblr-id-map.json";

/** アーティストページを持つタグ (tag slug → artist slug)。旧 /tagged/* をアーティストページへ寄せる */
const ARTIST_TAGS: Record<string, string> = {
	diastereomer: "diastereomer",
	sectcommune: "sect-commune",
	metafictions: "metafictions",
	sfh: "sfh",
	"the-twilight-states": "the-twilight-states",
	"dizzy-states": "dizzy-states",
	"fourier-analysis": "fourier-analysis",
};

const idMap = tumblrIdMap as Record<string, string>;

/** タグ名を seed と同じ規則 (python-slugify 相当) で slug 化する */
export function tagSlug(tag: string): string {
	return tag
		.normalize("NFKD")
		.replace(/[̀-ͯ]/g, "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "");
}

/**
 * 旧 Tumblr の URL パスを新サイトのパスに解決する。該当しなければ null
 * - /post/{id}[/{slug}] → /posts/{新slug}
 * - /tagged/{tag}[/page/n] → /artists/{slug} または /tag/{slug}
 * - /rss → /rss.xml, /archive[/...] → /posts, /page/{n} → /posts?page={n}
 */
export function resolveLegacyPath(pathname: string): string | null {
	let path: string;
	try {
		path = decodeURIComponent(pathname);
	} catch {
		path = pathname;
	}
	path = path.replace(/\/+$/, "") || "/";

	const post = /^\/post\/(\d+)(?:\/.*)?$/.exec(path);
	if (post) {
		const slug = idMap[post[1]];
		return slug ? `/posts/${slug}` : null;
	}

	const tagged = /^\/tagged\/([^/]+)(?:\/.*)?$/.exec(path);
	if (tagged) {
		const slug = tagSlug(tagged[1].replace(/\+/g, " "));
		if (!slug) return null;
		const artist = ARTIST_TAGS[slug];
		return artist ? `/artists/${artist}` : `/tag/${slug}`;
	}

	if (path === "/rss") return "/rss.xml";
	if (path === "/archive" || path.startsWith("/archive/")) return "/posts";
	const page = /^\/page\/(\d+)$/.exec(path);
	if (page) return Number(page[1]) > 1 ? `/posts?page=${page[1]}` : "/posts";
	return null;
}
