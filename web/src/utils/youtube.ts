const YOUTUBE_ID_RE =
	/(?:youtube(?:-nocookie)?\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/;

/** YouTube の URL から動画 ID を取り出す。YouTube でなければ null */
export function youtubeId(url: string | null | undefined): string | null {
	if (!url) return null;
	return YOUTUBE_ID_RE.exec(url)?.[1] ?? null;
}

/** Cookie を使わない埋め込み URL (Cookie 同意バナー不要にするため nocookie ドメインを使う) */
export function youtubeEmbedUrl(id: string): string {
	return `https://www.youtube-nocookie.com/embed/${id}`;
}

export function youtubeThumbnail(id: string): string {
	return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
}
