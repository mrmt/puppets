import type { APIRoute } from "astro";
import { getEmDashCollection } from "emdash";

import { getArtists } from "../utils/artists";

export const GET: APIRoute = async ({ site, url }) => {
	const base = (site?.toString() || `${url.origin}/`).replace(/\/$/, "");
	const { entries: posts } = await getEmDashCollection("posts", { orderBy: { published_at: "desc" } });
	const { artists } = await getArtists();

	const urls: { loc: string; lastmod?: Date | null }[] = [
		{ loc: `${base}/` },
		{ loc: `${base}/artists` },
		{ loc: `${base}/posts` },
		{ loc: `${base}/fa` },
		...artists.map((a) => ({ loc: `${base}/artists/${a.id}` })),
		...posts.map((p) => ({ loc: `${base}/posts/${p.id}`, lastmod: p.data.updatedAt ?? p.data.publishedAt })),
	];

	const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
	.map(
		(u) =>
			`  <url><loc>${encodeURI(u.loc)}</loc>${u.lastmod ? `<lastmod>${u.lastmod.toISOString()}</lastmod>` : ""}</url>`,
	)
	.join("\n")}
</urlset>`;

	return new Response(body, {
		headers: {
			"Content-Type": "application/xml; charset=utf-8",
			"Cache-Control": "public, max-age=3600",
		},
	});
};
