/**
 * OGP 画像をコンテンツ自身の素材から選ぶ。
 * 外部由来の素材 (YouTube サムネイル、リンク先のジャケット等) は scripts/backfill_og_images.py が
 * EmDash のメディアとして og_image フィールドに保存する。表示時に外部へ取りに行くことはしない
 */
import { mediaUrl } from "./media";
import { youtubeId, youtubeThumbnail } from "./youtube";

interface PostLike {
	data: { og_image?: unknown; video_url?: string | null; featured_image?: unknown; photos?: unknown };
}

/** 投稿の OGP 画像: 保存済み og_image → 写真 → (未保存の新しい投稿のみ) YouTube サムネイル。無ければ null */
export function ownPostImage(post: PostLike, origin: string): string | null {
	const photos = Array.isArray(post.data.photos) ? post.data.photos : [];
	const stored = mediaUrl(post.data.og_image) ?? mediaUrl(post.data.featured_image) ?? mediaUrl(photos[0]);
	if (stored) return new URL(stored, origin).href;
	const vid = youtubeId(post.data.video_url);
	return vid ? youtubeThumbnail(vid) : null;
}

/** 投稿リストの先頭から、素材を持つ最初の投稿の画像 (一覧・タグ・アーティストページ用) */
export function firstOwnImage(posts: PostLike[], origin: string): string | null {
	for (const post of posts) {
		const image = ownPostImage(post, origin);
		if (image) return image;
	}
	return null;
}
