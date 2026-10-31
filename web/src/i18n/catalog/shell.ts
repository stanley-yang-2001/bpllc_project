import type { Nine } from "./types";

/** Site text for navigation, header, layout and theme text. */
export const shell = {
  "nav.home": ["Home", "Inicio", "Accueil", "Startseite", "Home", "Início", "ホーム", "首页", "홈"],
  "nav.chat": ["Chat", "Chat", "Chat", "Chat", "Chat", "Chat", "チャット", "聊天", "채팅"],
  "nav.vocabulary": ["Vocabulary", "Vocabulario", "Vocabulaire", "Wortschatz", "Vocabolario", "Vocabulário", "語彙", "词汇", "어휘"],
  "nav.studio": ["Studio", "Estudio", "Studio", "Studio", "Studio", "Estúdio", "スタジオ", "创作室", "스튜디오"],
  "nav.library": ["Library", "Biblioteca", "Bibliothèque", "Bibliothek", "Libreria", "Biblioteca", "ライブラリ", "书库", "라이브러리"],
  "nav.practice": ["Practice", "Práctica", "Pratique", "Üben", "Pratica", "Prática", "練習", "练习", "연습"],
  "nav.settings": ["Settings", "Ajustes", "Réglages", "Einstellungen", "Impostazioni", "Configurações", "設定", "设置", "설정"],
  "nav.main": ["Main", "Principal", "Principal", "Hauptmenü", "Principale", "Principal", "メイン", "主导航", "메인"],
  "layout.studying": ["Studying", "Estudiando", "J'étudie", "Ich lerne", "Sto studiando", "Estudando", "学習中", "正在学习", "학습 중"],
  "layout.activeLanguage": ["Active language", "Idioma activo", "Langue active", "Aktive Sprache", "Lingua attiva", "Idioma ativo", "学習中の言語", "当前语言", "현재 언어"],
  "layout.logout": ["Log out", "Cerrar sesión", "Se déconnecter", "Abmelden", "Esci", "Sair", "ログアウト", "退出登录", "로그아웃"],
  "layout.privacy": ["Privacy Policy", "Política de privacidad", "Politique de confidentialité", "Datenschutzerklärung", "Informativa sulla privacy", "Política de privacidade", "プライバシーポリシー", "隐私政策", "개인정보 처리방침"],
  "theme.toDark": ["Switch to dark mode", "Cambiar al modo oscuro", "Passer en mode sombre", "Zum dunklen Modus wechseln", "Passa alla modalità scura", "Mudar para o modo escuro", "ダークモードに切り替える", "切换到深色模式", "다크 모드로 전환"],
  "theme.toLight": ["Switch to light mode", "Cambiar al modo claro", "Passer en mode clair", "Zum hellen Modus wechseln", "Passa alla modalità chiara", "Mudar para o modo claro", "ライトモードに切り替える", "切换到浅色模式", "라이트 모드로 전환"],
  "theme.darkTitle": ["Dark mode", "Modo oscuro", "Mode sombre", "Dunkler Modus", "Modalità scura", "Modo escuro", "ダークモード", "深色模式", "다크 모드"],
  "theme.lightTitle": ["Light mode", "Modo claro", "Mode clair", "Heller Modus", "Modalità chiara", "Modo claro", "ライトモード", "浅色模式", "라이트 모드"],
} as const satisfies Record<string, Nine>;
