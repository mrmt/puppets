/** EmDash の画像フィールド値 ($media で取り込んだもの等) から配信 URL を得る */
export function mediaUrl(value: unknown): string | null {
	if (!value || typeof value !== "object") return null;
	const media = value as Record<string, unknown>;
	if (typeof media.src === "string" && media.src) return media.src;
	const meta = media.meta as Record<string, unknown> | undefined;
	if (typeof meta?.storageKey === "string" && meta.storageKey) {
		return `/_emdash/api/media/file/${meta.storageKey}`;
	}
	return null;
}

export interface Photo {
	url: string;
	alt: string;
	width?: number;
	height?: number;
}

/** photos (json フィールド) を表示用に正規化する。解決できない要素は捨てる */
export function toPhotos(value: unknown): Photo[] {
	if (!Array.isArray(value)) return [];
	return value.flatMap((item) => {
		const url = mediaUrl(item);
		if (!url) return [];
		const m = item as Record<string, unknown>;
		return [
			{
				url,
				alt: typeof m.alt === "string" ? m.alt : "",
				width: typeof m.width === "number" ? m.width : undefined,
				height: typeof m.height === "number" ? m.height : undefined,
			},
		];
	});
}
