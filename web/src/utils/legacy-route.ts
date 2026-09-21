import type { APIRoute } from "astro";

import { resolveLegacyPath } from "./legacy";

/** 旧 Tumblr URL 用ルートの共通ハンドラ: 解決できれば 301、できなければ 404 ページ */
export const legacyRedirect: APIRoute = ({ url, redirect, rewrite }) => {
	const to = resolveLegacyPath(url.pathname);
	return to ? redirect(to, 301) : rewrite("/404");
};
