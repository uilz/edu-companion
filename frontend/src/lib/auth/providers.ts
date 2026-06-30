/**
 * 登录方式注册表
 *
 * 设计原则:
 * 1. 所有登录方式（本地账号 / OAuth）统一抽象成 Provider
 * 2. UI 层只消费注册表，不写死具体方式 → 新增 OAuth 只需追加一条记录
 * 3. 视觉分两类：
 *    - LocalForm: 共用同一组表单字段（username/email + password），通过 chip 切换
 *    - OAuth:     单独一排图标按钮（Google/GitHub/微信...）
 *
 * 未来扩展示例:
 *   { id: "google",  label: "Google",  isOAuth: true,  icon: <Chrome /> }
 *   { id: "github",  label: "GitHub",  isOAuth: true,  icon: <Github /> }
 *   { id: "wechat",  label: "微信",    isOAuth: true,  icon: <MessageCircle /> }
 */

import { Mail, User, type LucideIcon } from "lucide-react";

export type ProviderKind = "local" | "oauth";

export interface LocalLoginProvider {
  id: "username" | "email";
  kind: "local";
  label: string;            // 按钮上的文案
  shortLabel: string;       // 切换 chip 上的短文案
  fieldKey: "username" | "email";
  fieldLabel: string;
  fieldPlaceholder: string;
  fieldType: "text" | "email";
  fieldValidation?: {
    pattern?: string;
    title?: string;
  };
  icon: LucideIcon;
}

export interface OAuthProvider {
  id: string;               // "google" | "github" | "wechat" ...
  kind: "oauth";
  label: string;            // "Google" / "GitHub" / "微信"
  icon: LucideIcon;
  enabled: boolean;         // 后端未对接 OAuth 时为 false，自动隐藏按钮
}

export type LoginProvider = LocalLoginProvider | OAuthProvider;

export const LOCAL_PROVIDERS: LocalLoginProvider[] = [
  {
    id: "username",
    kind: "local",
    label: "用户名登录",
    shortLabel: "用户名",
    fieldKey: "username",
    fieldLabel: "用户名",
    fieldPlaceholder: "字母 / 数字 / 中文 / 下划线",
    fieldType: "text",
    fieldValidation: {
      pattern: "[a-zA-Z0-9_\\u4e00-\\u9fff]+",
      title: "只能包含字母、数字、下划线和中文",
    },
    icon: User,
  },
  {
    id: "email",
    kind: "local",
    label: "邮箱登录",
    shortLabel: "邮箱",
    fieldKey: "email",
    fieldLabel: "邮箱",
    fieldPlaceholder: "you@example.com",
    fieldType: "email",
    icon: Mail,
  },
];

export const OAUTH_PROVIDERS: OAuthProvider[] = [
  // 未来启用示例（保持空数组即不显示 OAuth 区域）:
  // { id: "google", kind: "oauth", label: "Google", icon: Chrome, enabled: false },
  // { id: "github", kind: "oauth", label: "GitHub", icon: Github, enabled: false },
];

export const ENABLED_OAUTH_PROVIDERS: OAuthProvider[] =
  OAUTH_PROVIDERS.filter((p) => p.enabled);
