import MediaSearchBlock from "./MediaSearchBlock";
import VideoEmbed from "./../media/VideoEmbed";

/** 视频块路由组件：判断内容是视频嵌入还是媒体搜索结果，分发到对应组件 */
export function VideoBlockRouter({ content }: { content: Record<string, unknown> }) {
  const url = (content.url as string) || "";
  const title = (content.title as string) || "";
  const thumbnail = (content.thumbnail as string) || "";
  const platforms = content.platforms as Array<unknown> | undefined;

  // 如果有 platforms 数组 → 是媒体搜索结果 → 使用 MediaSearchBlock 展示
  // If this has platforms array → it's a MediaSearch result → show MediaSearchBlock
  if (platforms && platforms.length > 0) {
    return <MediaSearchBlock content={content} />;
  }

  // 如果 URL 匹配视频平台 → 使用 VideoEmbed 嵌入播放
  // If URL looks like a video platform → embed it
  if (url && /bilibili\.com|youtu\.be|youtube\.com|\.mp4|\.webm/i.test(url)) {
    return <VideoEmbed url={url} title={title} thumbnail={thumbnail} />;
  }

  // 兜底：显示 MediaSearchBlock（兼容旧格式）
  // Fallback: show MediaSearchBlock (handles legacy format)
  return <MediaSearchBlock content={content} />;
}
