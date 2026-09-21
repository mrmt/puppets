import { getEmDashCollection, getEntryTerms } from "emdash";

export interface ArtistLink {
	label: string;
	url: string;
}

/** アーティスト一覧 (sort_order 昇順) */
export async function getArtists() {
	const { entries, cacheHint } = await getEmDashCollection("artists", {
		orderBy: { sort_order: "asc" },
	});
	return { artists: entries, cacheHint };
}

export function artistLinks(value: unknown): ArtistLink[] {
	if (!Array.isArray(value)) return [];
	return value.filter(
		(v): v is ArtistLink => !!v && typeof v === "object" && typeof v.label === "string" && typeof v.url === "string",
	);
}

type Artist = Awaited<ReturnType<typeof getArtists>>["artists"][number];

/** 投稿に付いたタグからアーティスト名を引く (カードのラベル用) */
export async function withArtistLabels<T extends { data: { id: string } }>(posts: T[], artists: Artist[]) {
	const byTag = new Map(artists.map((a) => [a.data.tag, a.data.name]));
	return Promise.all(
		posts.map(async (post) => {
			const terms = await getEntryTerms("posts", post.data.id, "tag");
			const label = terms.map((t) => byTag.get(t.slug)).find(Boolean) ?? null;
			return { post, label };
		}),
	);
}
