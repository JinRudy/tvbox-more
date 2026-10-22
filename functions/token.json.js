/**
 * Cloudflare Pages Function: 安全下线已停用的网盘 Token 接口 (/token.json)
 * 作用: 全面启用 100% 开源纯净 CMS 采集站点播模式，彻底杜绝个人网盘凭据泄露
 */

export async function onRequest(context) {
  return new Response(
    JSON.stringify(
      {
        status: 410,
        message: "Token service has been permanently decommissioned. Repository is 100% pure open-source CMS streams without cloud drive token dependency.",
      },
      null,
      2
    ),
    {
      status: 410,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    }
  );
}
