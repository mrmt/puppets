import { youtubeEmbedUrl, youtubeId } from "./youtube";

export interface EmbedTarget {
	kind: "video" | "player";
	src: string;
	/** player の高さ (px)。video は 16:9 */
	height?: number;
}

const SPOTIFY_RE = /^https:\/\/open\.spotify\.com\/(?:intl-[a-z]{2}\/)?(?:embed\/)?(album|track|playlist|artist|episode|show)\/([A-Za-z0-9]+)/;
const APPLE_RE = /^https:\/\/(?:embed\.)?music\.apple\.com\/([a-z]{2})\/(album|playlist|song|music-video)\/(.+)$/;

/**
 * URL を埋め込みプレイヤーの src に変換する。対応外なら null
 * - YouTube → youtube-nocookie
 * - Spotify の共有 URL / embed URL → open.spotify.com/embed/...
 * - Apple Music の共有 URL / embed URL → embed.music.apple.com/...
 */
export function toEmbed(url: string | null | undefined): EmbedTarget | null {
	if (!url) return null;
	const yt = youtubeId(url);
	if (yt) return { kind: "video", src: youtubeEmbedUrl(yt) };

	const sp = SPOTIFY_RE.exec(url);
	if (sp) {
		const height = sp[1] === "track" || sp[1] === "episode" ? 152 : 352;
		return { kind: "player", src: `https://open.spotify.com/embed/${sp[1]}/${sp[2]}`, height };
	}

	const ap = APPLE_RE.exec(url);
	if (ap) {
		const path = ap[3].split("?")[0];
		const height = ap[2] === "song" ? 175 : 450;
		return { kind: "player", src: `https://embed.music.apple.com/${ap[1]}/${ap[2]}/${path}`, height };
	}
	return null;
}

interface Span {
	_type: string;
	text?: string;
	marks?: string[];
}

interface Block {
	_type: string;
	_key?: string;
	markDefs?: { _key: string; _type: string; href?: string }[];
	children?: Span[];
	[key: string]: unknown;
}

/**
 * リンク 1 つだけの段落 (Tumblr のリンクカード由来など) を、埋め込み可能な URL なら embed ブロックに置き換える
 */
export function linkParagraphsToEmbeds<T extends Block>(blocks: T[] | null | undefined): (T | Block)[] {
	if (!Array.isArray(blocks)) return [];
	return blocks.map((block) => {
		if (block._type !== "block" || !Array.isArray(block.children)) return block;
		const spans = block.children.filter((c) => (c.text ?? "").trim() !== "");
		if (spans.length !== 1) return block;
		const markKey = spans[0].marks?.find((m) => block.markDefs?.some((d) => d._key === m && d._type === "link"));
		const href = block.markDefs?.find((d) => d._key === markKey)?.href;
		if (!href || !toEmbed(href)) return block;
		return { _type: "embed", _key: block._key ?? href, url: href };
	});
}
