#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py - Highly aesthetic, ANSI-colored Interactive Terminal Client & Command Documentation 
for the LEGEND Arabic Neuro-Symbolic Reasoning Engine.
"""

import sys
import os
import json
import time
import requests

# ANSI Color Codes for Premium Cyberpunk Terminal Aesthetics
C_BLUE = "\033[38;5;45m"
C_PURPLE = "\033[38;5;99m"
C_PINK = "\033[38;5;201m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_GOLD = "\033[33m"
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_UNDER = "\033[4m"

API_URL = "http://127.0.0.1:8000"

# Multilingual State and Translation Helper
active_lang = "en"

translations = {
    "en": {
        "banner_sub": "100% Hallucination-Free Multilingual Global Neuro-Symbolic Hybrid Reasoning Engine",
        "server_status": "FastAPI Server Semantic Status",
        "active_provider": "Active Cognitive Provider",
        "online": "ONLINE (Connected)",
        "offline": "OFFLINE (Not connected - please run start_api.sh)",
        "menu_title": "Choose an action to execute the dedicated cognitive procedure:",
        "menu_doc": "[1] 📖 Concept & Command Documentation",
        "menu_teach": "[2] 🎓 Teach a New Fact (Fact Ingestion)",
        "menu_query": "[3] 🔍 Safe Grounding Logical Query (Zero-Hallucination)",
        "menu_stats": "[4] 📊 Network Metrics & Stats Dashboard",
        "menu_sleep": "[5] 💤 Trigger Cognitive Sleep & Consolidate",
        "menu_evolve": "[6] 🧬 Genetic Rule Crossover & Mutation",
        "menu_induct": "[7] ✨ Automated Symbolic Rule Induction",
        "menu_socratic": "[8] 💭 Socratic Dialogue Simulation",
        "menu_sandbox": "[9] 🔬 Hypothetical Sandbox Thought Experiment",
        "menu_delete": "[10] 🗑️ Delete Node or Relationship Cascade",
        "menu_rules": "[11] 🧩 Rules Governance & Custom Rules",
        "menu_export": "[12] 📥 Export Workspace to JSON",
        "menu_import": "[13] 📤 Import Workspace from JSON",
        "menu_clear": "[0] ❌ Clear/Wipe Entire Semantic Memory",
        "menu_config": "[C] ⚙️ Configure LLM Provider & Model",
        "menu_workspace": "[W] 💼 Workspaces Governance & Switching",
        "menu_lang": "[L] 🌐 Change CLI Interface Language",
        "menu_exit": "[Q] 🚪 Exit Control Panel",
        "lang_switch_title": "🌐 CLI Language Selection",
        "lang_switch_prompt": "Select language / اختر اللغة (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ Language changed successfully!",
        "exit_msg": "🪐 Thank you for using the LEGEND reasoning engine. Goodbye!",
        "press_enter_main": "Press [Enter] to return to the main menu...",
        "press_enter_cont": "Press Enter to continue...",
        "invalid_selection": "⚠️ Invalid selection; please choose a valid option.",
    },
    "ar": {
        "banner_sub": "محرك الاستدلال العصبي الرمزي العالمي متعدد اللغات الخالي من الهلوسة بنسبة 100%",
        "server_status": "حالة خادم الـ FastAPI دلالياً",
        "active_provider": "المزود المعرفي النشط",
        "online": "ONLINE (متصل)",
        "offline": "OFFLINE (غير متصل - يرجى تشغيل start_api.sh)",
        "menu_title": "اختر رقماً لتنفيذ الإجراء المعرفي المخصص:",
        "menu_doc": "[1] 📖 دليل قراءة وفهم الأوامر الدلالية والمفاهيم",
        "menu_teach": "[2] 🎓 تلقين العقل حقيقة جديدة (Ingestion)",
        "menu_query": "[3] 🔍 استعلام منطقي آمن خالي من الهلوسة",
        "menu_stats": "[4] 📊 لوحة رصد إحصائيات الشبكة وقاعدة البيانات",
        "menu_sleep": "[5] 💤 تشغيل دورة الاسترخاء والنوم والتثبيت الدلالي",
        "menu_evolve": "[6] 🧬 محاكاة التطور الجيني وتزاوج القواعد المنطقية",
        "menu_induct": "[7] ✨ حث واستنباط القواعد وتعديتها تلقائياً",
        "menu_socratic": "[8] 💭 إجراء حوار سقراطي فلسفي لتصحيح يقين المعتقدات",
        "menu_sandbox": "[9] 🔬 بدء تجربة فكرية في فضاء افتراضي معزول",
        "menu_delete": "[10] 🗑️ حذف كيان كامل أو رابط دلالي محدد",
        "menu_rules": "[11] 🧩 حوكمة وإدارة القواعد المنطقية يدوياً",
        "menu_export": "[12] 📥 تصدير مساحة العمل بصيغة JSON",
        "menu_import": "[13] 📤 استيراد مساحة العمل من صيغة JSON",
        "menu_clear": "[0] ❌ تصفير وإفراغ الذاكرة الدلالية بالكامل",
        "menu_config": "[C] ⚙️ ضبط مزود الخدمة والنموذج اللغوي",
        "menu_workspace": "[W] 💼 إدارة وحوكمة مساحات العمل",
        "menu_lang": "[L] 🌐 تغيير لغة الواجهة",
        "menu_exit": "[Q] 🚪 الخروج من لوحة التحكم",
        "lang_switch_title": "🌐 اختيار لغة واجهة التحكم",
        "lang_switch_prompt": "اختر اللغة / Select language (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ تم تغيير لغة الواجهة بنجاح!",
        "exit_msg": "🪐 شكراً لاستخدامك نظام LEGEND الاستدلالي. وداعاً!",
        "press_enter_main": "اضغط [Enter] للعودة إلى القائمة الرئيسية...",
        "press_enter_cont": "اضغط Enter للاستمرار...",
        "invalid_selection": "⚠️ اختيار خاطئ؛ يرجى تحديد رقم صحيح.",
    },
    "fr": {
        "banner_sub": "Moteur de raisonnement hybride neuro-symbolique 100% sans hallucination",
        "server_status": "Statut sémantique du serveur FastAPI",
        "active_provider": "Fournisseur cognitif actif",
        "online": "EN LIGNE (Connecté)",
        "offline": "HORS LIGNE (Non connecté - veuillez exécuter start_api.sh)",
        "menu_title": "Choisissez une action pour exécuter la procédure cognitive dédiée:",
        "menu_doc": "[1] 📖 Documentation conceptuelle et des commandes",
        "menu_teach": "[2] 🎓 Enseigner un nouveau fait (Fact Ingestion)",
        "menu_query": "[3] 🔍 Requête logique sécurisée (Zéro Hallucination)",
        "menu_stats": "[4] 📊 Tableau de bord des statistiques de connaissances",
        "menu_sleep": "[5] 💤 Lancer le cycle de sommeil cognitif",
        "menu_evolve": "[6] 🧬 Évolution génétique et croisement des règles",
        "menu_induct": "[7] ✨ Induction automatique des règles logiques",
        "menu_socratic": "[8] 💭 Simulation de débat socratique",
        "menu_sandbox": "[9] 🔬 Expérience de pensée dans la Sandbox virtuelle",
        "menu_delete": "[10] 🗑️ Supprimer entité ou relation",
        "menu_rules": "[11] 🧩 Gouvernance des règles logiques personnalisées",
        "menu_clear": "[0] ❌ Effacer toute la mémoire sémantique",
        "menu_lang": "[L] 🌐 Changer la langue du terminal",
        "menu_exit": "[Q] 🚪 Quitter le panneau de contrôle",
        "lang_switch_title": "🌐 Sélection de la langue du terminal",
        "lang_switch_prompt": "Choisir la langue (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ Langue changée avec succès!",
        "exit_msg": "🪐 Merci d'utiliser le moteur de raisonnement LEGEND. Au revoir!",
        "press_enter_main": "Appuyez sur [Entrée] pour revenir au menu principal...",
        "press_enter_cont": "Appuyez sur Entrée pour continuer...",
        "invalid_selection": "⚠️ Sélection invalide; veuillez choisir une option valide.",
    },
    "es": {
        "banner_sub": "Motor de razonamiento híbrido neuro-simbólico 100% libre de alucinaciones",
        "server_status": "Estado semántico del servidor FastAPI",
        "active_provider": "Proveedor cognitivo activo",
        "online": "EN LÍNEA (Conectado)",
        "offline": "FUERA DE LÍNEA (No conectado - por favor ejecute start_api.sh)",
        "menu_title": "Elija una acción para ejecutar el procedimiento cognitivo dedicado:",
        "menu_doc": "[1] 📖 Documentación de conceptos y comandos",
        "menu_teach": "[2] 🎓 Enseñar un novo hecho (Fact Ingestion)",
        "menu_query": "[3] 🔍 Consulta lógica segura (Cero Alucinación)",
        "menu_stats": "[4] 📊 Panel de estadísticas y métricas de red",
        "menu_sleep": "[5] 💤 Iniciar ciclo de sueño cognitivo",
        "menu_evolve": "[6] 🧬 Evolución genética y cruce de reglas",
        "menu_induct": "[7] ✨ Inducción automática de reglas lógicas",
        "menu_socratic": "[8] 💭 Simulación de debate socrático",
        "menu_sandbox": "[9] 🔬 Experimento de pensamiento en Sandbox virtual",
        "menu_delete": "[10] 🗑️ Eliminar entidad o relación",
        "menu_rules": "[11] 🧩 Gobernanza de reglas lógicas personalizadas",
        "menu_clear": "[0] ❌ Borrar toda la memoria semántica",
        "menu_lang": "[L] 🌐 Cambiar el idioma del terminal",
        "menu_exit": "[Q] 🚪 Salir del panel de control",
        "lang_switch_title": "🌐 Selección de idioma del terminal",
        "lang_switch_prompt": "Seleccione el idioma (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ ¡Idioma cambiado con éxito!",
        "exit_msg": "🪐 ¡Gracias por usar el motor de razonamiento LEGEND. Adiós!",
        "press_enter_main": "Presione [Enter] para volver al menú principal...",
        "press_enter_cont": "Presione Enter para continuar...",
        "invalid_selection": "⚠️ Selección no válida; elija una opción válida.",
    },
    "zh": {
        "banner_sub": "100% 无幻觉阿拉伯语和全球神经符号混合推理引擎",
        "server_status": "FastAPI 服务器语义状态",
        "active_provider": "活跃认知提供商",
        "online": "在线 (已连接)",
        "offline": "离线 (未连接 - 请运行 start_api.sh)",
        "menu_title": "选择要执行的专用认知程序操作:",
        "menu_doc": "[1] 📖 概念和命令文档",
        "menu_teach": "[2] 🎓 传授新事实 (事实摄入)",
        "menu_query": "[3] 🔍 安全接地逻辑查询 (零幻觉)",
        "menu_stats": "[4] 📊 网络指标和统计仪表板",
        "menu_sleep": "[5] 💤 触发认知睡眠并巩固",
        "menu_evolve": "[6] 🧬 遗传规则交叉与突变",
        "menu_induct": "[7] ✨ 自动符号规则归纳",
        "menu_socratic": "[8] 💭 苏格拉底对话模拟",
        "menu_sandbox": "[9] 🔬 假设沙盒思想实验",
        "menu_delete": "[10] 🗑️ 删除节点或关系级联",
        "menu_rules": "[11] 🧩 规则治理和自定义规则",
        "menu_clear": "[0] ❌ 清除/擦除整个语义内存",
        "menu_lang": "[L] 🌐 更改命令行界面语言",
        "menu_exit": "[Q] 🚪 退出控制面板",
        "lang_switch_title": "🌐 命令行界面语言选择",
        "lang_switch_prompt": "选择语言 (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ 语言更改成功！",
        "exit_msg": "🪐 感谢您使用 LEGEND 推理引擎。再见！",
        "press_enter_main": "按 [Enter] 返回主菜单...",
        "press_enter_cont": "按回车键继续...",
        "invalid_selection": "⚠️ 无效的选择；请选择一个有效的选项。",
    },
    "tr": {
        "banner_sub": "%100 Halüsinasyonsuz Arapça & Küresel Nöro-Sembolik Hibrit Muhakeme Motoru",
        "server_status": "FastAPI Sunucusu Semantik Durumu",
        "active_provider": "Aktif Bilişsel Sağlayıcı",
        "online": "ÇEVRİMİÇİ (Bağlı)",
        "offline": "ÇEVRİMDIŞI (Bağlı değil - lütfen start_api.sh çalıştırın)",
        "menu_title": "Özel bilişsel prosedürü yürütmek için bir işlem seçin:",
        "menu_doc": "[1] 📖 Kavram & Komut Dokümantasyonu",
        "menu_teach": "[2] 🎓 Yeni Bir Gerçek Öğret (Gerçek Alımı)",
        "menu_query": "[3] 🔍 Güvenli Temellendirilmiş Mantıksal Sorgu (Sıfır Halüsinasyon)",
        "menu_stats": "[4] 📊 Ağ Metrikleri & İstatistik Gösterge Paneli",
        "menu_sleep": "[5] 💤 Bilişsel Uykuyu Tetikle & Konsolide Et",
        "menu_evolve": "[6] 🧬 Genetik Kural Çaprazlama & Mutasyonu",
        "menu_induct": "[7] ✨ Otomatik Sembolik Kural Çıkarımı",
        "menu_socratic": "[8] 💭 Sokratik Diyalog Simülasyonu",
        "menu_sandbox": "[9] 🔬 Hipotetik Sandbox Düşünce Deneyi",
        "menu_delete": "[10] 🗑️ Düğüm Veya İlişki Silme",
        "menu_rules": "[11] 🧩 Kural Yönetimi & Özel Kurallar",
        "menu_clear": "[0] ❌ Tüm Semantik Belleği Temizle/Sil",
        "menu_lang": "[L] 🌐 Terminal Arayüzü Dilini Değiştir",
        "menu_exit": "[Q] 🚪 Kontrol Panelinden Çık",
        "lang_switch_title": "🌐 Terminal Dili Seçimi",
        "lang_switch_prompt": "Dil seçin (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ Dil başarıyla değiştirildi!",
        "exit_msg": "🪐 LEGEND muhakeme motorunu kullandığınız için teşekkür ederiz. Hoşça kalın!",
        "press_enter_main": "Ana menüye dönmek için [Enter]'a basın...",
        "press_enter_cont": "Devam etmek için Enter'a basın...",
        "invalid_selection": "⚠️ Geçersiz seçim; lütfen geçerli bir seçenek belirleyin.",
    },
    "de": {
        "banner_sub": "100% halluzinationsfreie neuro-symbolische Hybrid-Reasoning-Engine",
        "server_status": "Semantischer Status des FastAPI-Servers",
        "active_provider": "Aktiver kognitiver Anbieter",
        "online": "ONLINE (Verbunden)",
        "offline": "OFFLINE (Nicht verbunden - bitte start_api.sh ausführen)",
        "menu_title": "Wählen Sie eine Aktion aus, um das kognitive Verfahren auszuführen:",
        "menu_doc": "[1] 📖 Konzept- und Befehlsdokumentation",
        "menu_teach": "[2] 🎓 Neuen Fakt lehren (Faktenaufnahme)",
        "menu_query": "[3] 🔍 Sichere logische Abfrage (Null Halluzination)",
        "menu_stats": "[4] 📊 Dashboard für Netzwerkmetriken und Statistiken",
        "menu_sleep": "[5] 💤 Kognitiven Schlafzyklus auslösen & konsolidieren",
        "menu_evolve": "[6] 🧬 Genetische Regelkreuzung & Mutation",
        "menu_induct": "[7] ✨ Automatische Induktion symbolischer Regeln",
        "menu_socratic": "[8] 💭 Sokratische Dialogsimulation",
        "menu_sandbox": "[9] 🔬 Gedankenexperiment in virtueller Sandbox",
        "menu_delete": "[10] 🗑️ Konzept oder Beziehung kaskadierend löschen",
        "menu_rules": "[11] 🧩 Regelverwaltung & benutzerdefinierte Regeln",
        "menu_clear": "[0] ❌ Gesamten semantischen Speicher löschen",
        "menu_lang": "[L] 🌐 CLI-Sprache ändern",
        "menu_exit": "[Q] 🚪 Kontrollfeld verlassen",
        "lang_switch_title": "🌐 CLI-Sprachauswahl",
        "lang_switch_prompt": "Sprache wählen (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ Sprache erfolgreich geändert!",
        "exit_msg": "🪐 Vielen Dank, dass Sie die LEGEND-Reasoning-Engine verwendet haben. Auf Wiedersehen!",
        "press_enter_main": "Drücken Sie [Enter], um zum Hauptmenü zurückzukehren...",
        "press_enter_cont": "Drücken Sie Enter, um fortzufahren...",
        "invalid_selection": "⚠️ Ungültige Auswahl; Bitte wählen Sie eine gültige Option.",
    },
    "ru": {
        "banner_sub": "100% гибридный нейро-символический процессор рассуждений без галлюцинаций",
        "server_status": "Семантический статус сервера FastAPI",
        "active_provider": "Активный когнитивный провайдер",
        "online": "В СЕТИ (Подключен)",
        "offline": "ВНЕ СЕТИ (Нет подключения - пожалуйста, запустите start_api.sh)",
        "menu_title": "Выберите действие для запуска когнитивной процедуры:",
        "menu_doc": "[1] 📖 Документация концепций и команд",
        "menu_teach": "[2] 🎓 Обучить новому факту (Fact Ingestion)",
        "menu_query": "[3] 🔍 Безопасный логический запрос (Ноль галлюцинаций)",
        "menu_stats": "[4] 📊 Панель метрик сети и статистики",
        "menu_sleep": "[5] 💤 Запустить когнитивный цикл сна и консолидации",
        "menu_evolve": "[6] 🧬 Генетическое скрещивание и мутация правил",
        "menu_induct": "[7] ✨ Автоматическая индукция символических правил",
        "menu_socratic": "[8] 💭 Моделирование сократического диалога",
        "menu_sandbox": "[9] 🔬 Мысленный эксперимент в виртуальной песочнице",
        "menu_delete": "[10] 🗑️ Удалить сущность или отношение",
        "menu_rules": "[11] 🧩 Управление правилами и кастомные правила",
        "menu_clear": "[0] ❌ Очистить всю семантическую память",
        "menu_lang": "[L] 🌐 Изменить язык терминала",
        "menu_exit": "[Q] 🚪 Выйти из панели управления",
        "lang_switch_title": "🌐 Выбор языка терминала",
        "lang_switch_prompt": "Выберите язык (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ Язык успешно изменен!",
        "exit_msg": "🪐 Спасибо за использование системы рассуждений LEGEND. До свидания!",
        "press_enter_main": "Нажмите [Enter] для возврата в главное меню...",
        "press_enter_cont": "Нажмите Enter для продолжения...",
        "invalid_selection": "⚠️ Неверный выбор; пожалуйста, выберите корректную опцию.",
    },
    "pt": {
        "banner_sub": "Motor de raciocínio híbrido neuro-simbólico 100% livre de alucinações",
        "server_status": "Status semântico do servidor FastAPI",
        "active_provider": "Provedor cognitivo ativo",
        "online": "ONLINE (Conectado)",
        "offline": "OFFLINE (Não conectado - execute start_api.sh)",
        "menu_title": "Escolha uma ação para executar o procedimento cognitivo dedicado:",
        "menu_doc": "[1] 📖 Documentação de conceitos e comandos",
        "menu_teach": "[2] 🎓 Ensinar um novo fato (Ingestão de fatos)",
        "menu_query": "[3] 🔍 Consulta lógica segura (Zero Alucinação)",
        "menu_stats": "[4] 📊 Painel de métricas e estatísticas de rede",
        "menu_sleep": "[5] 💤 Iniciar ciclo de sono cognitivo e consolidar",
        "menu_evolve": "[6] 🧬 Evolução genética e cruzamento de regras",
        "menu_induct": "[7] ✨ Indução automática de regras simbólicas",
        "menu_socratic": "[8] 💭 Simulação de diálogo socrático",
        "menu_sandbox": "[9] 🔬 Experimento de pensamento em Sandbox virtual",
        "menu_delete": "[10] 🗑️ Excluir conceito ou relação em cascata",
        "menu_rules": "[11] 🧩 Governança de regras e regras personalizadas",
        "menu_clear": "[0] ❌ Limpar toda a memória semântica",
        "menu_lang": "[L] 🌐 Alterar o idioma do terminal",
        "menu_exit": "[Q] 🚪 Sair do painel de controle",
        "lang_switch_title": "🌐 Seleção de idioma do terminal",
        "lang_switch_prompt": "Selecione o idioma (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ Idioma alterado com sucesso!",
        "exit_msg": "🪐 Obrigado por usar o motor de raciocínio LEGEND. Adeus!",
        "press_enter_main": "Pressione [Enter] para retornar ao menu principal...",
        "press_enter_cont": "Pressione Enter para continuar...",
        "invalid_selection": "⚠️ Seleção inválida; escolha uma opção válida.",
    },
    "ja": {
        "banner_sub": "100%ハルシネーションフリーのアラビア語・グローバル神経記号論理ハイブリッド推論エンジン",
        "server_status": "FastAPIサーバーのセマンティック状態",
        "active_provider": "アクティブな認知プロバイダー",
        "online": "オンライン (接続中)",
        "offline": "オフライン (未接続 - start_api.shを実行してください)",
        "menu_title": "専用の認知プロシージャを実行するアクションを選択してください:",
        "menu_doc": "[1] 📖 概念とコマンドのドキュメント",
        "menu_teach": "[2] 🎓 新しい事実を学習 (事実の取り込み)",
        "menu_query": "[3] 🔍 安全なグラウンディング論理クエリ (ハルシネーションゼロ)",
        "menu_stats": "[4] 📊 ネットワークメトリクスと統計のダッシュボード",
        "menu_sleep": "[5] 💤 認知睡眠サイクルを起動して統合",
        "menu_evolve": "[6] 🧬 遺伝的規則の交差と突然変異",
        "menu_induct": "[7] ✨ 自動記号規則の誘導",
        "menu_socratic": "[8] 💭 ソクラテス式対話シミュレーション",
        "menu_sandbox": "[9] 🔬 仮想サンドボックスの思考実験",
        "menu_delete": "[10] 🗑️ ノードまたは関係の連鎖削除",
        "menu_rules": "[11] 🧩 規則ガバナンスとカスタム規則",
        "menu_clear": "[0] ❌ セマンティックメモリ全体をクリア/消去",
        "menu_lang": "[L] 🌐 ターミナルの表示言語を変更",
        "menu_exit": "[Q] 🚪 コントロールパネルを終了",
        "lang_switch_title": "🌐 ターミナル表示言語の選択",
        "lang_switch_prompt": "言語を選択してください (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ 表示言語を変更しました！",
        "exit_msg": "🪐 LEGEND推論エンジンをご利用いただきありがとうございました。さようなら！",
        "press_enter_main": "[Enter] を押してメインメニューに戻ります...",
        "press_enter_cont": "Enterを押して続行します...",
        "invalid_selection": "⚠️ 無効な選択です。有効なオプションを選択してください。",
    },
    "ko": {
        "banner_sub": "100% 환각 없는 아랍어 및 글로벌 신경-기호 하이브리드 추론 엔진",
        "server_status": "FastAPI 서버 의미론적 상태",
        "active_provider": "활성 인지 제공자",
        "online": "온라인 (연결됨)",
        "offline": "오프라인 (연결되지 않음 - start_api.sh를 실행하십시오)",
        "menu_title": "전용 인지 절차를 실행할 작업을 선택하십시오:",
        "menu_doc": "[1] 📖 개념 및 명령 문서",
        "menu_teach": "[2] 🎓 새로운 사실 교육 (사실 수집)",
        "menu_query": "[3] 🔍 안전한 접지 논리 쿼리 (환각 제로)",
        "menu_stats": "[4] 📊 네트워크 메트릭 및 통계 대시보드",
        "menu_sleep": "[5] 💤 인지 수면 주기 트리거 및 통합",
        "menu_evolve": "[6] 🧬 유전 규칙 교차 및 변이",
        "menu_induct": "[7] ✨ 자동 기호 규칙 귀납",
        "menu_socratic": "[8] 💭 소크라테스 대화 시뮬레이션",
        "menu_sandbox": "[9] 🔬 가상 샌드박스 사고 실험",
        "menu_delete": "[10] 🗑️ 노드 또는 관계 연쇄 삭제",
        "menu_rules": "[11] 🧩 규칙 거버넌스 및 사용자 정의 규칙",
        "menu_clear": "[0] ❌ 의미론적 메모리 전체 지우기",
        "menu_lang": "[L] 🌐 터미널 표시 언어 변경",
        "menu_exit": "[Q] 🚪 제어판 종료",
        "lang_switch_title": "🌐 터미널 표시 언어 선택",
        "lang_switch_prompt": "언어를 선택하십시오 (en, ar, fr, es, zh, tr, de, ru, pt, ja, ko): ",
        "lang_switch_success": "✅ 언어가 성공적으로 변경되었습니다!",
        "exit_msg": "🪐 LEGEND 추론 엔진을 이용해 주셔서 감사합니다. 안녕히 가십시오!",
        "press_enter_main": "[Enter]를 눌러 메인 메뉴로 돌아갑니다...",
        "press_enter_cont": "계속하려면 Enter를 누르십시오...",
        "invalid_selection": "⚠️ 잘못된 선택입니다. 유효한 옵션을 선택하십시오.",
    }
}

def t(key, **kwargs):
    global active_lang
    lang_dict = translations.get(active_lang, translations["en"])
    text = lang_dict.get(key, translations["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

# Default configuration fallback
config = {
    "provider": "google",
    "model": "gemini-2.5-flash",
    "api_key": ""
}

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_banner():
    banner = f"""
{C_BLUE}{C_BOLD}==================================================================================
   🪐  L E G E N D   N E U R O - S Y M B O L I C   C O G N I T I V E   C L I  🪐
=================================================================================={C_RESET}
    {C_CYAN}{t('banner_sub')}{C_RESET}
    {C_PURPLE}Headless API Console & Interactive Concept Grounding Client v4.0{C_RESET}
"""
    print(banner)

def check_server() -> bool:
    """Check if the FastAPI backend is running."""
    try:
        response = requests.get(f"{API_URL}/api/stats", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False

def show_documentation():
    clear_terminal()
    show_banner()
    if active_lang == 'ar':
        doc = f"""
{C_GOLD}{C_BOLD}📖 دليل الأوامر الدلالية والمفاهيم العصبية الرمزية (Command & API Index):{C_RESET}

{C_CYAN}{C_BOLD}1. التلقين والامتصاص المعرفي (Fact Learning - Ingestion){C_RESET}
   {C_BOLD}• الأمر:{C_RESET} `/api/learn`
   {C_BOLD}• الغرض:{C_RESET} تحويل الجمل الطبيعية إلى علاقات ثلاثية دلالية (Triples) وتصنيفها في فئات (Taxonomy).
   {C_BOLD}• الحماية الدلالية:{C_RESET} يمرر النص عبر كاشف التناقضات (Contradiction Filter) للتأكد من عدم تعارضه 
     مع الحقائق المسجلة مسبقاً قبل حفظه في شبكة الذاكرة الحية وقاعدة SQLite.

{C_PINK}{C_BOLD}2. الاستعلام الدلالي الخالي من الهلوسة (Pure DB Reasoning - RAG Grounding){C_RESET}
   {C_BOLD}• الأمر:{C_RESET} `/api/query`
   {C_BOLD}• الغرض:{C_RESET} الإجابة عن الأسئلة عبر عزل الشبكة الفرعية المرتبطة بالمفاهيم، وصياغة الرد منطقياً.
   {C_BOLD}• الميزة الفائقة:{C_RESET} يضمن {C_GREEN}خلو الإجابة من الهلوسة بنسبة 100%{C_RESET} لأن النموذج اللغوي يتقيد حرفياً 
     بالحقائق المستخرجة والعلاقات المثبتة منطقياً في قاعدة البيانات ولا يخمن أي معلومة خارجية.

{C_PURPLE}{C_BOLD}3. دورة النوم والاسترخاء المعرفي (Cognitive Sleep Cycle){C_RESET}
   {C_BOLD}• الأمر:{C_RESET} `/api/sleep`
   {C_BOLD}• الغرض:{C_RESET} محاكاة النوم البيولوجي لـ التقوية، التقليم، والاستقرار المعرفي.

{C_GREEN}{C_BOLD}4. حث وتوليد القواعد الرمزية تلقائياً (Symbolic Rule Induction){C_RESET}
   {C_BOLD}• الأمر:{C_RESET} `/api/rules/induct`
   {C_BOLD}• الغرض:{C_RESET} مسح الشبكة دلالياً والبحث عن مسارات مغلقة متكررة لتوليد قوانين استدلالية.

{C_BLUE}{C_BOLD}5. التطور الجيني للقواعد (Genetic Rule Crossover & Mutation){C_RESET}
   {C_BOLD}• الأمر:{C_RESET} `/api/rules/evolve`
   {C_BOLD}• الغرض:{C_RESET} تطبيق خوارزمية جينية لتزويج قواعد منطقية وإحداث طفرات عشوائية.

{C_GOLD}{C_BOLD}6. الحوار السقراطي المعرفي (Socratic Dialogue Simulation){C_RESET}
   {C_BOLD}• الأمر:{C_RESET} `/api/socratic/dialogue`
   {C_BOLD}• الغرض:{C_RESET} مساءلة الذات وتفنيد المعتقدات العميقة.

{C_CYAN}{C_BOLD}7. التجارب الفكرية الافتراضية المعزولة (Hypothetical Sandbox){C_RESET}
   {C_BOLD}• الأمر:{C_RESET} `/api/thought_experiment/run`
   {C_BOLD}• الغرض:{C_RESET} محاكاة الفرضيات في بيئة معزولة بالكامل دون المساس بالذاكرة الحقيقية.
"""
    else:
        doc = f"""
{C_GOLD}{C_BOLD}📖 Semantic Commands & Neuro-Symbolic Concept Directory (Command & API Index):{C_RESET}

{C_CYAN}{C_BOLD}1. Fact Learning & Ingestion{C_RESET}
   {C_BOLD}• Endpoint:{C_RESET} `/api/learn`
   {C_BOLD}• Purpose:{C_RESET} Convert natural language sentences into semantic triples and classify them into taxonomies.
   {C_BOLD}• Semantic Filter:{C_RESET} Passes text through a Contradiction Filter to ensure it does not conflict with existing facts.

{C_PINK}{C_BOLD}2. Zero-Hallucination Grounded Query (Pure DB Reasoning){C_RESET}
   {C_BOLD}• Endpoint:{C_RESET} `/api/query`
   {C_BOLD}• Purpose:{C_RESET} Answer questions by isolating the relevant sub-network of concepts and reasoning mathematically.
   {C_BOLD}• Premium Benefit:{C_RESET} Guarantees {C_GREEN}100% hallucination-free answers{C_RESET} by binding the LLM strictly to the database.

{C_PURPLE}{C_BOLD}3. Cognitive Sleep & Consolidation Cycle{C_RESET}
   {C_BOLD}• Endpoint:{C_RESET} `/api/sleep`
   {C_BOLD}• Purpose:{C_RESET} Simulate biological sleep to strengthen frequent links, prune weak relationships, and run transitive reasoning.

{C_GREEN}{C_BOLD}4. Symbolic Rule Induction{C_RESET}
   {C_BOLD}• Endpoint:{C_RESET} `/api/rules/induct`
   {C_BOLD}• Purpose:{C_RESET} Mine semantic patterns and closed-loop paths to discover new logical inference rules automatically.

{C_BLUE}{C_BOLD}5. Genetic Rule Crossover & Mutation{C_RESET}
   {C_BOLD}• Endpoint:{C_RESET} `/api/rules/evolve`
   {C_BOLD}• Purpose:{C_RESET} Execute genetic crossover and confidence mutation algorithms to accelerate machine learning deduction.

{C_GOLD}{C_BOLD}6. Socratic Self-Doubt Dialogue Simulation{C_RESET}
   {C_BOLD}• Endpoint:{C_RESET} `/api/socratic/dialogue`
   {C_BOLD}• Purpose:{C_RESET} Run interactive philosophical debates questioning deep network beliefs to revise confidence levels.

{C_CYAN}{C_BOLD}7. Isolated Hypothetical Thought Sandbox{C_RESET}
   {C_BOLD}• Endpoint:{C_RESET} `/api/thought_experiment/run`
   {C_BOLD}• Purpose:{C_RESET} Create isolated clone sandboxes to simulate hypotheticals without modifying the main database.
"""
    print(doc)
    input(f"\n{C_BOLD}{t('press_enter_main')}{C_RESET}")

def load_or_prompt_config():
    global config
    if config["api_key"]:
        return
        
    print(f"\n{C_GOLD}⚙️ إعداد الاتصال بالنموذج اللغوي (أول مرة):{C_RESET}")
    provider = input(f"➔ اختر المزود ({C_CYAN}google{C_RESET} / {C_PURPLE}openrouter{C_RESET} / {C_PINK}groq{C_RESET} / {C_GREEN}local{C_RESET}) [الافتراضي: google]: ").strip().lower()
    if provider in ["google", "openrouter", "groq", "local"]:
        config["provider"] = provider
        
    if config["provider"] == "google":
        config["model"] = "gemini-2.5-flash"
    elif config["provider"] == "openrouter":
        config["model"] = "google/gemini-2.5-flash"
    elif config["provider"] == "groq":
        config["model"] = "llama-3.3-70b-versatile"
    elif config["provider"] == "local":
        local_models = []
        try:
            res = requests.get(f"{API_URL}/api/local_models", timeout=2)
            if res.status_code == 200:
                local_models = res.json().get("models", [])
        except Exception:
            pass
        if not local_models:
            models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
            if os.path.exists(models_dir):
                local_models = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
        
        if local_models:
            print(f"\n{C_GREEN}📦 النماذج المحلية المكتشفة ({len(local_models)}):{C_RESET}")
            for idx, lm in enumerate(local_models, 1):
                print(f"  [{idx}] {lm}")
            sel = input(f"➔ اختر رقم النموذج [الافتراضي: 1]: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(local_models):
                config["model"] = local_models[int(sel) - 1]
            else:
                config["model"] = local_models[0]
        else:
            config["model"] = "local-model.gguf"
            print(f"{C_RED}⚠️ لم يتم العثور على أي نموذج محلي (.gguf) في مجلد models/{C_RESET}")
        
    if config["provider"] != "local":
        model = input(f"➔ أدخل اسم الموديل [الافتراضي: {config['model']}]: ").strip()
        if model:
            config["model"] = model
            
        key = input(f"➔ أدخل مفتاح الـ {C_GOLD}API Key{C_RESET} المخصص للتشغيل: ").strip()
        if key:
            config["api_key"] = key
        else:
            print(f"{C_RED}⚠️ تنبيه: لم يتم إدخال مفتاح API. بعض العمليات التوليدية قد تفشل.{C_RESET}")
            time.sleep(1)
    else:
        config["api_key"] = "local"


def interactive_teach():
    load_or_prompt_config()
    while True:
        clear_terminal()
        show_banner()
        
        # Fetch active curiosity challenges from the Curiosity Engine
        try:
            curiosity_res = requests.get(f"{API_URL}/api/curiosity?limit=2", timeout=1.5)
            if curiosity_res.status_code == 200:
                curiosity_data = curiosity_res.json()
                questions = curiosity_data.get("questions", [])
                if questions:
                    print(f"\n{C_GOLD}{C_BOLD}🤔 العقل المعرفي يشعر بالفضول حالياً ويتساءل:{C_RESET}")
                    for q in questions:
                        print(f"  {C_PURPLE}➔ {q['question']}{C_RESET}")
                    print("-" * 65)
        except Exception:
            pass # Silently proceed if curiosity engine fails or server is slow
            
        print(f"\n{C_CYAN}{C_BOLD}🎓 تلقين حقيقة جديدة إلى العقل العصبي الرمزي (مستمر):{C_RESET}")
        print("➔ اكتب بياناً أو مادة قانونية/طبية جديدة للدمج (أو أجب عن أحد أسئلة الفضول أعلاه).")
        print(f"➔ اضغط {C_GOLD}[Enter]{C_RESET} دون كتابة شيء للعودة إلى القائمة الرئيسية.")
        sentence = input(f"\n{C_BOLD}✍️ النص: {C_RESET}").strip()
        
        if not sentence:
            break
            
        payload = {
            "sentence": sentence,
            **config
        }
        
        print(f"\n⏳ جاري إرسال النص، إجراء الفحص الدلالي وامتصاص الكيانات...")
        try:
            res = requests.post(f"{API_URL}/api/learn", json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "contradiction":
                    print(f"\n{C_RED}🚨 [كاشف التناقض المنطقي]: تم رفض الدمج المباشر لوجود تعارض منطقي!{C_RESET}")
                    for c in data.get("contradictions", []):
                        print(f"   ⚠️ {c}")
                elif data.get("status") == "success":
                    print(f"\n{C_GREEN}✅ تم امتصاص الحقائق بنجاح وإضافتها لقاعدة المعرفة والشبكة الرسومية!{C_RESET}")
                    print(f"\n{C_GOLD}📊 خطوات الرصد الاستدلالي الصادرة:{C_RESET}")
                    for log in data.get("logs", []):
                        print(f"  ➔ {log}")
                else:
                    print(f"\n{C_RED}❌ فشل: {data.get('response')}{C_RESET}")
            else:
                print(f"\n{C_RED}❌ خطأ من الخادم (FastAPI): {res.text}{C_RESET}")
        except Exception as e:
            print(f"\n{C_RED}❌ فشل الاتصال بالخادم: {e}{C_RESET}")
            
        input(f"\n{C_BOLD}اضغط [Enter] لتلقين حقيقة أخرى...{C_RESET}")

def interactive_query():
    load_or_prompt_config()
    while True:
        clear_terminal()
        show_banner()
        print(f"\n{C_PINK}{C_BOLD}🔍 استعلام منطقي آمن (Zero-Hallucination Query - مستمر):{C_RESET}")
        print("➔ اطرح سؤالاً حول الحقائق أو البنود الملقنة.")
        print(f"➔ اضغط {C_GOLD}[Enter]{C_RESET} دون كتابة شيء للعودة إلى القائمة الرئيسية.")
        sentence = input(f"\n{C_BOLD}❓ السؤال: {C_RESET}").strip()
        
        if not sentence:
            break
            
        payload = {
            "sentence": sentence,
            **config
        }
        
        print(f"\n⏳ جاري عزل الحقائق المرتبطة وصياغة الرد المنطقي بالمنطق الخالي من الهلوسة...")
        try:
            res = requests.post(f"{API_URL}/api/query", json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    print(f"\n{C_GREEN}💬 إجابة العقل المعرفي الموثوقة:{C_RESET}")
                    print(f"{C_BOLD}{data.get('response')}{C_RESET}")
                    
                    print(f"\n{C_GOLD}🧾 خطوات الرصد ومسارات الربط الدلالية (Deductive Trace):{C_RESET}")
                    for log in data.get("logs", []):
                        print(f"  ➔ {log}")
                else:
                    print(f"\n{C_RED}❌ فشل الاستعلام: {data.get('response')}{C_RESET}")
            else:
                print(f"\n{C_RED}❌ خطأ من الخادم: {res.text}{C_RESET}")
        except Exception as e:
            print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
            
        input(f"\n{C_BOLD}اضغط [Enter] لطرح سؤال آخر...{C_RESET}")

def run_cognitive_operation(endpoint: str, title: str, log_key: str = "logs"):
    clear_terminal()
    show_banner()
    
    print(f"\n{C_PURPLE}{C_BOLD}⚡ جاري تشغيل العملية الدلالية: {title}...{C_RESET}")
    try:
        res = requests.post(f"{API_URL}{endpoint}")
        if res.status_code == 200:
            data = res.json()
            print(f"\n{C_GREEN}✅ اكتملت العملية بنجاح!{C_RESET}")
            
            # Print stats if it's the sleep cycle
            if "stats" in data:
                stats = data["stats"]
                print(f"\n{C_CYAN}{C_BOLD}🌙 نتائج دورة النوم والتوحيد الدلالي:{C_RESET}")
                print(f"  ➔ {C_GREEN}الروابط المترادفة المكتشفة والدمج دلالياً:{C_RESET} {stats.get('synonyms_linked', 0)}")
                print(f"  ➔ {C_GREEN}الروابط الجديدة المستنتجة بالتعدي والوراثة:{C_RESET} {stats.get('new_inferences', 0)}")
                print(f"  ➔ {C_GOLD}الروابط المقواة نتيجة للتكرار في نفس السياق:{C_RESET} {stats.get('edges_strengthened', 0)}")
                print(f"  ➔ {C_GOLD}أحلام العقل ( Dream discoveries) والترابطات:{C_RESET} {stats.get('dream_discoveries', 0)}")
                print(f"  ➔ {C_RED}الروابط المعرفية الضعيفة المقلمة لمنع التشتت:{C_RESET} {stats.get('edges_pruned', 0)}")
                print(f"  ➔ {C_RED}عقد الضوضاء الصوتية والعبارات المهملة المحذوفة:{C_RESET} {stats.get('noise_nodes_cleaned', 0)}")
            
            # Print logs if available
            logs = data.get(log_key, [])
            if logs:
                print(f"\n{C_GOLD}📊 سجلات العملية المعرفية تفصيلياً:{C_RESET}")
                for log in logs:
                    print(f"  ➔ {log}")
            elif not data.get("stats"):
                print(f"\n{C_GOLD}📊 نتائج العملية:{C_RESET}")
                print(f"  {data.get('message', 'اكتملت العملية بدون سجلات إضافية.')}")
        else:
            print(f"\n{C_RED}❌ فشل تنفيذ العملية على الخادم: {res.text}{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
        
    input(f"\n{C_BOLD}اضغط [Enter] للاستمرار...{C_RESET}")

def run_socratic_lab():
    clear_terminal()
    show_banner()
    load_or_prompt_config()
    
    print(f"\n{C_GOLD}{C_BOLD}💭 بدء حوار سقراطي شكاك مع الذات (Self-Skeptic dialogue):{C_RESET}")
    print("سيقوم النظام المعرفي باختيار أحد معتقداته العميقة ومساءلتها فلسفياً لتعديل يقينها...")
    time.sleep(1)
    
    print(f"\n⏳ جاري إطلاق الحوار السقراطي المعقد...")
    try:
        res = requests.post(f"{API_URL}/api/socratic/dialogue", json=config)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                print(f"\n{C_CYAN}🎭 تفاصيل مسرحية الحوار السقراطي المعرفي:{C_RESET}")
                # Print script lines beautifully
                lines = data.get("dialogue", "").split("\n")
                for line in lines:
                    if line.strip():
                        print(f" {line}")
                
                print(f"\n{C_GREEN}⚙️ النتيجة والقرار المعرفي المتخذ:{C_RESET}")
                print(f" 🏆 القرار: {C_BOLD}{data.get('decision')}{C_RESET} بشأن المعتقد [{data.get('belief')}]")
                for log in data.get("logs", []):
                    print(f" ➔ {log}")
            else:
                print(f"\n{C_RED}❌ فشل: {data.get('response')}{C_RESET}")
        else:
            print(f"\n{C_RED}❌ خطأ من الخادم: {res.text}{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
        
    input(f"\n{C_BOLD}اضغط [Enter] للاستمرار...{C_RESET}")

def run_thought_sandbox_lab():
    clear_terminal()
    show_banner()
    load_or_prompt_config()
    
    print(f"\n{C_CYAN}{C_BOLD}🔬 تشغيل تجربة فكرية افتراضية (Hypothetical Thought Sandbox):{C_RESET}")
    print("اكتب فرضية افتراضية مؤقتة لقياس تأثيراتها وتفرعاتها على الشبكة الدلالية:")
    hypothesis = input(f"\n{C_BOLD}🔮 الفرضية الافتراضية: {C_RESET}").strip()
    
    if not hypothesis:
        return
        
    payload = {
        "hypothesis": hypothesis,
        **config
    }
    
    print(f"\n⏳ جاري عزل العقل، بناء المحاكاة، واستنتاج التبعات منطقياً...")
    try:
        res = requests.post(f"{API_URL}/api/thought_experiment/run", json=payload)
        if res.status_code == 200:
            data = res.json()
            print(f"\n{C_GREEN}✅ اكتملت تجربة الفرضية المعزولة بنجاح!{C_RESET}")
            print(f"\n{C_GOLD}📊 سجلات محاكاة التبعات الاستدلالية:{C_RESET}")
            for log in data.get("logs", []):
                print(f"  ➔ {log}")
                
            if data.get("contradictions"):
                print(f"\n{C_RED}🚨 تناقضات تم حجب حدوثها وحمايتها في الواقع المعرفي الحقيقي:{C_RESET}")
                for c in data.get("contradictions"):
                    print(f"  ⚠️ {c}")
                    
            if data.get("hypothetical_edges"):
                print(f"\n{C_CYAN}🔮 تعديلات وعلاقات دلالية مؤقتة ناتجة عن الفرضية:{C_RESET}")
                for e in data.get("hypothetical_edges"):
                    print(f"  ➔ ({e['source']} ➔ {e['relation']} ➔ {e['target']}) بـيقين {e['confidence']:.2f}")
        else:
            print(f"\n{C_RED}❌ فشل تشغيل المحاكاة: {res.text}{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
        
    input(f"\n{C_BOLD}اضغط [Enter] للاستمرار...{C_RESET}")

def view_live_metrics():
    clear_terminal()
    show_banner()
    
    print(f"\n{C_CYAN}{C_BOLD}📊 لوحة رصد إحصائيات قاعدة البيانات والذاكرة الرسومية الحية:{C_RESET}")
    try:
        res = requests.get(f"{API_URL}/api/stats")
        if res.status_code == 200:
            stats = res.json()
            
            # Fetch rules list to calculate size
            rules_res = requests.get(f"{API_URL}/api/rules")
            rules_count = len(rules_res.json()) if rules_res.status_code == 200 else 0
            
            print(f"\n {C_BOLD}• المفاهيم والعقد بالذاكرة الحية (Nodes):{C_RESET} {C_GREEN}{stats.get('total_concepts')}{C_RESET}")
            print(f" {C_BOLD}• العلاقات والحقائق المسجلة (Triples):{C_RESET} {C_GREEN}{stats.get('total_triples')}{C_RESET}")
            print(f" {C_BOLD}• الحالات والأفراد المسجلين (Instances):{C_RESET} {C_GREEN}{stats.get('total_instances')}{C_RESET}")
            print(f" {C_BOLD}• قواعد الاستدلال النشطة (Rules):{C_RESET} {C_GREEN}{rules_count}{C_RESET}")
            print(f" {C_BOLD}• عمق شجرة الوراثة الفئوية (Longest Tax Path):{C_RESET} {C_GOLD}{stats.get('max_depth')}{C_RESET}")
            print(f" {C_BOLD}• الحجم الفعلي لقاعدة SQLite المعرفية:{C_RESET} {C_GOLD}{stats.get('db_size_kb')} KB{C_RESET}")
            
            if stats.get("top_connected"):
                print(f"\n{C_PURPLE}🏆 أكثر الكيانات ترابطاً بالشبكة المعرفية:{C_RESET}")
                for node, deg in stats.get("top_connected"):
                    print(f"  ➔ الكيان: {C_BOLD}'{node}'{C_RESET} ➔ عدد الروابط المباشرة: {C_CYAN}{deg}{C_RESET}")
                    
            if stats.get("top_predicates"):
                print(f"\n{C_PINK}🔗 أكثر العلاقات شيوعاً واستخداماً بالذاكرة:{C_RESET}")
                for pred, count in stats.get("top_predicates"):
                    print(f"  ➔ العلاقة: {C_BOLD}'{pred}'{C_RESET} ➔ تكرار الاستخدام: {C_CYAN}{count}{C_RESET}")
        else:
            print(f"\n{C_RED}❌ فشل الحصول على الإحصائيات: {res.text}{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
        
    input(f"\n{C_BOLD}اضغط [Enter] للاستمرار...{C_RESET}")

def wipe_knowledge():
    clear_terminal()
    show_banner()
    
    print(f"\n{C_RED}{C_BOLD}🚨 تصفير وإفراغ العقل المعرفي وقاعدة البيانات بالكامل:{C_RESET}")
    confirm = input(f"{C_RED}⚠️ هل أنت متأكد تماماً من حذف كافة الحقائق والقواعد والرموز المسجلة؟ (yes/no): {C_RESET}").strip().lower()
    if confirm == "yes":
        try:
            res = requests.post(f"{API_URL}/api/clear")
            if res.status_code == 200:
                print(f"\n{C_GREEN}✅ تم تصفير العقل وقاعدة البيانات خالية تماماً الآن وبانتظار تلقين جديد!{C_RESET}")
            else:
                print(f"\n{C_RED}❌ فشل التصفير: {res.text}{C_RESET}")
        except Exception as e:
            print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
    else:
        print(f"\n{C_GREEN}👍 تم إلغاء عملية الحذف؛ الأنطولوجيا سليمة ولم تمس.{C_RESET}")
        
    input(f"\n{C_BOLD}اضغط [Enter] للاستمرار...{C_RESET}")

def interactive_delete_element():
    while True:
        clear_terminal()
        show_banner()
        print(f"{C_RED}{C_BOLD}🗑️ لوحة إدارة واستعراض وحذف الكيانات والروابط (Semantic Ontology Manager):{C_RESET}\n")
        print(f"  {C_GOLD}{C_BOLD}[1]{C_RESET} 📥 استعراض العلاقات المضافة في آخر جلسة تلقين")
        print(f"  {C_GOLD}{C_BOLD}[2]{C_RESET} ↩️ التراجع الفوري وحذف علاقات آخر تلقين (Undo)")
        print(f"  {C_GOLD}{C_BOLD}[3]{C_RESET} 🔍 استعراض وبحث وتصفح كافة العلاقات بالأنطولوجيا (Pagination)")
        print(f"  {C_GOLD}{C_BOLD}[4]{C_RESET} 🗑️ حذف رابط دلالي محدد (Delete Relation Triple)")
        print(f"  {C_GOLD}{C_BOLD}[5]{C_RESET} 💥 حذف كيان بالكامل مع حذف تعاقبي لعلاقاته (Cascade Delete Concept)")
        print(f"  {C_GOLD}{C_BOLD}[B]{C_RESET} العودة للقائمة الرئيسية")
        print("-" * 75)
        sub_choice = input(f"{C_BOLD}➔ اختر الإجراء: {C_RESET}").strip().lower()
        
        if sub_choice == 'b':
            break
        elif sub_choice == '1':
            try:
                res = requests.get(f"{API_URL}/api/triples/latest")
                if res.status_code == 200:
                    triples = res.json().get("triples", [])
                    print(f"\n{C_CYAN}{C_BOLD}📥 العلاقات المضافة في آخر تلقين ({len(triples)}):{C_RESET}")
                    if not triples:
                        print("   لا توجد علاقات مضافة حديثاً.")
                    for i, t in enumerate(triples, 1):
                        print(f"  {i}. ({t['source']} ➔ {t['relation']} ➔ {t['target']})")
                else:
                    print(f"\n{C_RED}❌ فشل الجلب: {res.text}{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
            
        elif sub_choice == '2':
            confirm = input(f"\n{C_RED}⚠️ هل تريد حقاً التراجع الفوري وحذف علاقات آخر جلسة تلقين؟ (yes/no): {C_RESET}").strip().lower()
            if confirm == 'yes':
                try:
                    res = requests.delete(f"{API_URL}/api/triples/latest")
                    if res.status_code == 200:
                        data = res.json()
                        print(f"\n{C_GREEN}✅ {data.get('message')}{C_RESET} (تم حذف {data.get('deleted_count')} علاقة)")
                    else:
                        print(f"\n{C_RED}❌ فشل الحذف: {res.text}{C_RESET}")
                except Exception as e:
                    print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
            else:
                print(f"\n{C_GREEN}👍 تم الحفاظ على العلاقات ملقنة.{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
            
        elif sub_choice == '3':
            page = 1
            limit = 10
            query = None
            q_input = input(f"\n{C_BOLD}➔ أدخل كلمة بحث عربية (أو اضغط Enter لعرض الكل): {C_RESET}").strip()
            if q_input:
                query = q_input
            
            while True:
                try:
                    url = f"{API_URL}/api/triples?page={page}&limit={limit}"
                    if query:
                        url += f"&query={requests.utils.quote(query)}"
                    
                    res = requests.get(url)
                    if res.status_code == 200:
                        data = res.json()
                        total = data.get("total", 0)
                        pages = data.get("pages", 0)
                        triples = data.get("triples", [])
                        
                        clear_terminal()
                        show_banner()
                        print(f"{C_CYAN}{C_BOLD}🔍 استعراض وتصفح العلاقات بالأنطولوجيا:{C_RESET}")
                        if query:
                            print(f"🕵️ تصفية البحث بـ: '{C_GOLD}{query}{C_RESET}'")
                        print(f"📊 إجمالي العلاقات المطابقة: {C_GOLD}{total}{C_RESET} | صفحة: {C_GOLD}{page}{C_RESET} من {C_GOLD}{pages}{C_RESET}\n")
                        
                        if not triples:
                            print("   لا توجد علاقات في هذه الصفحة.")
                        else:
                            for idx, t in enumerate(triples, 1):
                                idx_global = (page - 1) * limit + idx
                                print(f"  {idx_global}. ({t['source']} ➔ {t['relation']} ➔ {t['target']}) | يقين = {t['confidence']}")
                        
                        print("-" * 65)
                        print(f"  {C_GOLD}[N]{C_RESET} الصفحة التالية | {C_GOLD}[P]{C_RESET} الصفحة السابقة | {C_GOLD}[B]{C_RESET} العودة للوحة الإدارة")
                        print("-" * 65)
                        nav = input(f"{C_BOLD}➔ اختر الإجراء: {C_RESET}").strip().lower()
                        if nav == 'n':
                            if page < pages:
                                page += 1
                            else:
                                print(f"{C_RED}⚠️ هذه هي الصفحة الأخيرة.{C_RESET}")
                                time.sleep(1)
                        elif nav == 'p':
                            if page > 1:
                                page -= 1
                            else:
                                print(f"{C_RED}⚠️ هذه هي الصفحة الأولى.{C_RESET}")
                                time.sleep(1)
                        elif nav == 'b':
                            break
                    else:
                        print(f"\n{C_RED}❌ فشل الجلب: {res.text}{C_RESET}")
                        input(f"\n{C_GOLD}اضغط Enter للعودة...{C_RESET}")
                        break
                except Exception as e:
                    print(f"\n{C_RED}❌ تعذر الاتصال بالخادم: {e}{C_RESET}")
                    input(f"\n{C_GOLD}اضغط Enter للعودة...{C_RESET}")
                    break
                    
        elif sub_choice == '4':
            sub = input(f"\n{C_BOLD}➔ أدخل الكيان الأول (Subject - مثال: التفاح): {C_RESET}").strip()
            pred = input(f"{C_BOLD}➔ أدخل العلاقة الدلالية (Predicate - مثال: لون): {C_RESET}").strip()
            obj = input(f"{C_BOLD}➔ أدخل الكيان الثاني (Object - مثال: أحمر): {C_RESET}").strip()
            if not (sub and pred and obj):
                print(f"\n{C_RED}❌ يجب ملء جميع الحقول الثلاثة للعلاقة.{C_RESET}")
                time.sleep(2)
                continue
            try:
                res = requests.delete(f"{API_URL}/api/triples", json={"source": sub, "relation": pred, "target": obj})
                if res.status_code == 200:
                    print(f"\n{C_GREEN}✅ {res.json().get('message', 'تم حذف العلاقة بنجاح')}{C_RESET}")
                else:
                    print(f"\n{C_RED}❌ فشل الحذف: {res.text}{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}❌ خطأ اتصال بالخادم: {str(e)}{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
            
        elif sub_choice == '5':
            concept_name = input(f"\n{C_BOLD}➔ أدخل اسم الكيان المراد حذفه نهائياً بالكامل (مثال: أحمد): {C_RESET}").strip()
            if not concept_name:
                continue
            confirm = input(f"{C_RED}⚠️ سيؤدي ذلك إلى حذف الكيان وحذف تعاقبي لكافة علاقاته المرتبطة. هل تريد الاستمرار؟ (yes/no): {C_RESET}").strip().lower()
            if confirm == 'yes':
                try:
                    res = requests.delete(f"{API_URL}/api/concepts/{requests.utils.quote(concept_name)}")
                    if res.status_code == 200:
                        print(f"\n{C_GREEN}✅ {res.json().get('message')}{C_RESET}")
                    else:
                        print(f"\n{C_RED}❌ فشل الحذف: {res.text}{C_RESET}")
                except Exception as e:
                    print(f"\n{C_RED}❌ خطأ اتصال بالخادم: {str(e)}{C_RESET}")
            else:
                print(f"\n{C_GREEN}👍 تم إلغاء عملية الحذف التعاقبي.{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")

def interactive_rules_governance():
    while True:
        clear_terminal()
        show_banner()
        print(f"{C_PURPLE}{C_BOLD}🧩 لوحة حوكمة وإدارة القواعد المنطقية يدوياً (Rules Governance):{C_RESET}\n")
        print(f"  {C_GOLD}{C_BOLD}[1]{C_RESET} عرض كافة القواعد المنطقية المسجلة حالياً")
        print(f"  {C_GOLD}{C_BOLD}[2]{C_RESET} إضافة قاعدة استدلال منطقية جديدة يدوياً")
        print(f"  {C_GOLD}{C_BOLD}[3]{C_RESET} حذف قاعدة منطقية بالاسم")
        print(f"  {C_GOLD}{C_BOLD}[B]{C_RESET} العودة للقائمة الرئيسية")
        print("-" * 65)
        sub_choice = input(f"{C_BOLD}➔ اختر الإجراء: {C_RESET}").strip().lower()
        
        if sub_choice == 'b':
            break
        elif sub_choice == '1':
            try:
                res = requests.get(f"{API_URL}/api/stats")
                if res.status_code == 200:
                    stats = res.json()
                    rules = stats.get("active_rules", [])
                    print(f"\n{C_CYAN}{C_BOLD}📋 القواعد المنطقية النشطة بالشبكة ({len(rules)}):{C_RESET}")
                    if not rules:
                        print("  لا توجد قواعد منطقية مسجلة حالياً.")
                    for rule in rules:
                        print(f"\n  • {C_GOLD}{C_BOLD}الاسم:{C_RESET} {rule.get('name')}")
                        print(f"    - {C_BOLD}معامل اليقين (Confidence):{C_RESET} {rule.get('confidence')}")
                        print(f"    - {C_BOLD}شروط القاعدة (Antecedents):{C_RESET} {rule.get('antecedents')}")
                        print(f"    - {C_BOLD}النتيجة المترتبة (Consequent):{C_RESET} {rule.get('consequent')}")
                else:
                    print(f"\n{C_RED}❌ فشل جلب القواعد: {res.text}{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}❌ خطأ اتصال بالخادم: {str(e)}{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
        elif sub_choice == '2':
            rule_name = input(f"\n{C_BOLD}➔ أدخل اسم القاعدة بالإنجليزية (مثال: my_rule): {C_RESET}").strip()
            confidence = input(f"{C_BOLD}➔ أدخل نسبة يقين القاعدة (من 0.0 إلى 1.0 - مثال: 0.95): {C_RESET}").strip()
            print(f"\n{C_CYAN}{C_BOLD}⚠️ شروط القاعدة (كل شرط 3 عناصر مفصولة بفاصلة، مثال: ?x, صديق, ?y):{C_RESET}")
            antecedents = []
            while True:
                ant = input(f"   - الشرط #{len(antecedents)+1} (أو اضغط Enter لإنهاء الشروط): {C_RESET}").strip()
                if not ant:
                    break
                antecedents.append(ant)
            consequent = input(f"{C_BOLD}➔ أدخل النتيجة المترتبة (Consequent - مثال: ?x, يعرف, ?y): {C_RESET}").strip()
            
            if not (rule_name and confidence and antecedents and consequent):
                print(f"\n{C_RED}❌ يجب ملء جميع الحقول المطلوبة.{C_RESET}")
                time.sleep(2)
                continue
            try:
                conf_val = float(confidence)
            except ValueError:
                print(f"\n{C_RED}❌ معامل اليقين يجب أن يكون رقماً عشرياً.{C_RESET}")
                time.sleep(2)
                continue
                
            try:
                payload = {
                    "rule_name": rule_name,
                    "confidence": conf_val,
                    "antecedents": antecedents,
                    "consequent": consequent
                }
                res = requests.post(f"{API_URL}/api/rules", json=payload)
                if res.status_code == 200:
                    print(f"\n{C_GREEN}✅ {res.json().get('message', 'تمت إضافة القاعدة بنجاح')}{C_RESET}")
                else:
                    print(f"\n{C_RED}❌ فشل إضافة القاعدة: {res.text}{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}❌ خطأ اتصال بالخادم: {str(e)}{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
        elif sub_choice == '3':
            rule_name = input(f"\n{C_BOLD}➔ أدخل اسم القاعدة المراد حذفها بدقة: {C_RESET}").strip()
            if not rule_name:
                continue
            try:
                res = requests.delete(f"{API_URL}/api/rules/{rule_name}")
                if res.status_code == 200:
                    print(f"\n{C_GREEN}✅ {res.json().get('message', 'تم حذف القاعدة بنجاح')}{C_RESET}")
                else:
                    print(f"\n{C_RED}❌ فشل الحذف: {res.text}{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}❌ خطأ اتصال بالخادم: {str(e)}{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")

def interactive_export_workspace():
    clear_terminal()
    show_banner()
    if active_lang == 'ar':
        print(f"\n{C_CYAN}{C_BOLD}📥 تصدير مساحة العمل الحالية أو المحددة بصيغة JSON:{C_RESET}")
        print("   (اترك الحقل فارغاً لتصدير مساحة العمل النشطة حالياً)")
        ws_name = input(f"{C_BOLD}➔ أدخل اسم مساحة العمل المراد تصديرها: {C_RESET}").strip()
    else:
        print(f"\n{C_CYAN}{C_BOLD}📥 Export Workspace to JSON format:{C_RESET}")
        print("   (Leave empty to export the currently active workspace)")
        ws_name = input(f"{C_BOLD}➔ Enter the name of the workspace to export: {C_RESET}").strip()

    try:
        params = {}
        if ws_name:
            params["name"] = ws_name
        
        if active_lang == 'ar':
            print(f"\n⏳ جاري استخراج البيانات من خادم الاستدلال...")
        else:
            print(f"\n⏳ Querying active data from the reasoning server...")
            
        res = requests.get(f"{API_URL}/api/workspace/export", params=params, timeout=5)
        if res.status_code == 200:
            data = res.json()
            ws_actual_name = data.get("workspace_name", "workspace")
            concepts = data.get("concepts", [])
            triples = data.get("triples", [])
            rules = data.get("rules", [])
            
            # Clean filename using actual workspace name or user entered name
            clean_name = "".join([c if c.isalnum() or c in [' ', '_', '-'] else '_' for c in ws_actual_name]).strip()
            clean_name = clean_name.replace(' ', '_')
            default_filename = f"{clean_name}_export.json"
            
            if active_lang == 'ar':
                print(f"\n{C_GREEN}✅ تم جلب البيانات بنجاح!{C_RESET}")
                print(f"   • اسم مساحة العمل المستهدفة: {C_GOLD}{ws_actual_name}{C_RESET}")
                print(f"   • عدد المفاهيم (Concepts): {len(concepts)}")
                print(f"   • عدد العلاقات الثلاثية (Triples): {len(triples)}")
                print(f"   • عدد القواعد المنطقية (Rules): {len(rules)}")
                print("-" * 50)
                out_path = input(f"{C_BOLD}➔ حدد مسار حفظ الملف [{default_filename}]: {C_RESET}").strip()
            else:
                print(f"\n{C_GREEN}✅ Data fetched successfully!{C_RESET}")
                print(f"   • Workspace Target Name: {C_GOLD}{ws_actual_name}{C_RESET}")
                print(f"   • Concepts Count: {len(concepts)}")
                print(f"   • Triples Count: {len(triples)}")
                print(f"   • Rules Count: {len(rules)}")
                print("-" * 50)
                out_path = input(f"{C_BOLD}➔ Select JSON save path [{default_filename}]: {C_RESET}").strip()
                
            if not out_path:
                out_path = default_filename
                
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            abs_path = os.path.abspath(out_path)
            if active_lang == 'ar':
                print(f"\n{C_GREEN}🎉 تم تصدير مساحة العمل بنجاح وحفظ الملف في:{C_RESET}")
                print(f"   {C_BOLD}{abs_path}{C_RESET}")
            else:
                print(f"\n{C_GREEN}🎉 Workspace exported successfully and saved to:{C_RESET}")
                print(f"   {C_BOLD}{abs_path}{C_RESET}")
        else:
            if active_lang == 'ar':
                print(f"\n{C_RED}❌ فشل التصدير: {res.text}{C_RESET}")
            else:
                print(f"\n{C_RED}❌ Export failed: {res.text}{C_RESET}")
    except Exception as e:
        if active_lang == 'ar':
            print(f"\n{C_RED}❌ خطأ أثناء التصدير: {str(e)}{C_RESET}")
        else:
            print(f"\n{C_RED}❌ Error during export: {str(e)}{C_RESET}")
            
    if active_lang == 'ar':
        input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
    else:
        input(f"\n{C_GOLD}Press Enter to continue...{C_RESET}")

def interactive_import_workspace():
    clear_terminal()
    show_banner()
    if active_lang == 'ar':
        print(f"\n{C_CYAN}{C_BOLD}📤 استيراد مساحة عمل كاملة من ملف JSON:{C_RESET}")
        file_path = input(f"{C_BOLD}➔ أدخل مسار ملف الـ JSON المراد استيراده: {C_RESET}").strip()
    else:
        print(f"\n{C_CYAN}{C_BOLD}📤 Import entire workspace from a JSON file:{C_RESET}")
        file_path = input(f"{C_BOLD}➔ Enter JSON file path to import: {C_RESET}").strip()
        
    if not file_path or not os.path.exists(file_path):
        if active_lang == 'ar':
            print(f"\n{C_RED}❌ الملف غير موجود أو المسار خاطئ.{C_RESET}")
            input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
        else:
            print(f"\n{C_RED}❌ File not found or path is incorrect.{C_RESET}")
            input(f"\n{C_GOLD}Press Enter to continue...{C_RESET}")
        return
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
            
        ws_name = payload.get("workspace_name", "")
        concepts = payload.get("concepts", [])
        triples = payload.get("triples", [])
        rules = payload.get("rules", [])
        
        if active_lang == 'ar':
            print(f"\n{C_CYAN}📋 معلومات الملف المستورد:{C_RESET}")
            print(f"   • اسم مساحة العمل المعرّف: {C_GOLD}{ws_name}{C_RESET}")
            print(f"   • المفاهيم المتاحة: {len(concepts)}")
            print(f"   • العلاقات الدلالية: {len(triples)}")
            print(f"   • القواعد المنطقية: {len(rules)}")
            print("-" * 50)
            ws_override = input(f"{C_BOLD}➔ أدخل اسماً جديداً لمساحة العمل أو اضغط Enter للإبقاء على [{ws_name}]: {C_RESET}").strip()
        else:
            print(f"\n{C_CYAN}📋 Imported File Metadata:{C_RESET}")
            print(f"   • Defined Workspace Name: {C_GOLD}{ws_name}{C_RESET}")
            print(f"   • Concepts Count: {len(concepts)}")
            print(f"   • Triples Count: {len(triples)}")
            print(f"   • Rules Count: {len(rules)}")
            print("-" * 50)
            ws_override = input(f"{C_BOLD}➔ Enter a new workspace name or press Enter to keep [{ws_name}]: {C_RESET}").strip()
            
        final_ws_name = ws_override if ws_override else ws_name
        if not final_ws_name:
            if active_lang == 'ar':
                print(f"\n{C_RED}❌ يجب تحديد اسم لمساحة العمل لإتمام الاستيراد.{C_RESET}")
                input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
            else:
                print(f"\n{C_RED}❌ Workspace name is required to proceed with import.{C_RESET}")
                input(f"\n{C_GOLD}Press Enter to continue...{C_RESET}")
            return
            
        payload["workspace_name"] = final_ws_name
        if "mode" not in payload:
            payload["mode"] = "active"
            
        if active_lang == 'ar':
            print(f"\n⏳ جاري إرسال البيانات وحفظها في خادم الاستدلال (هذا الإجراء يمسح الجداول السابقة لمساحة العمل)...")
        else:
            print(f"\n⏳ Transmitting workspace data and saving to reasoning server (this overwrites existing data in the target workspace)...")
            
        res = requests.post(f"{API_URL}/api/workspace/import", json=payload, timeout=10)
        if res.status_code == 200:
            if active_lang == 'ar':
                print(f"\n{C_GREEN}🎉 تم استيراد وتفعيل مساحة العمل [{final_ws_name}] بنجاح تام!{C_RESET}")
            else:
                print(f"\n{C_GREEN}🎉 Workspace [{final_ws_name}] imported and activated successfully!{C_RESET}")
        else:
            if active_lang == 'ar':
                print(f"\n{C_RED}❌ فشل الاستيراد: {res.text}{C_RESET}")
            else:
                print(f"\n{C_RED}❌ Import failed: {res.text}{C_RESET}")
    except Exception as e:
        if active_lang == 'ar':
            print(f"\n{C_RED}❌ خطأ أثناء الاستيراد: {str(e)}{C_RESET}")
        else:
            print(f"\n{C_RED}❌ Error during import: {str(e)}{C_RESET}")
            
    if active_lang == 'ar':
        input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
    else:
        input(f"\n{C_GOLD}Press Enter to continue...{C_RESET}")

def interactive_workspaces_governance():
    clear_terminal()
    show_banner()
    if active_lang == 'ar':
        print(f"\n{C_CYAN}{C_BOLD}💼 إدارة وحوكمة مساحات العمل المعرفية (Workspaces):{C_RESET}")
    else:
        print(f"\n{C_CYAN}{C_BOLD}💼 Cognitive Workspaces Governance & Switching:{C_RESET}")
        
    try:
        res = requests.get(f"{API_URL}/api/workspaces", timeout=3)
        if res.status_code != 200:
            if active_lang == 'ar':
                print(f"\n{C_RED}⚠️ خادم الاستدلال الحالي يعمل في وضع مساحة العمل الفردية الموحدة ولا يدعم تعدد مساحات العمل.{C_RESET}")
                input(f"\n{C_GOLD}اضغط Enter للاستمرار...{C_RESET}")
            else:
                print(f"\n{C_RED}⚠️ The active reasoning server operates in single-workspace mode and does not support multi-workspaces.{C_RESET}")
                input(f"\n{C_GOLD}Press Enter to continue...{C_RESET}")
            return
            
        workspaces = res.json()
        print(f"\n{C_GOLD}{C_BOLD}📋 مساحات العمل الحالية بالشبكة ({len(workspaces)}):{C_RESET}")
        ws_list = list(workspaces.keys())
        for idx, ws in enumerate(ws_list, 1):
            ws_info = workspaces[ws]
            mode = ws_info.get("mode", "active")
            db = ws_info.get("db_filename", "ontology.db")
            print(f"  [{idx}] {C_BOLD}{ws}{C_RESET} ➔ {C_PURPLE}الوضع: {mode}{C_RESET} | {C_BLUE}قاعدة البيانات: {db}{C_RESET}")
            
        print("-" * 65)
        if active_lang == 'ar':
            print("  [s] اختيار مساحة عمل نشطة")
            print("  [a] إضافة مساحة عمل جديدة")
            print("  [d] حذف مساحة عمل نهائياً")
            print("  [b] العودة للقائمة الرئيسية")
        else:
            print("  [s] Select Active Workspace")
            print("  [a] Add New Workspace")
            print("  [d] Delete a Workspace")
            print("  [b] Return to Main Menu")
            
        sub_choice = input(f"\n{C_BOLD}➔ {t('menu_title')} {C_RESET}").strip().lower()
        if sub_choice == 'b':
            return
        elif sub_choice == 's':
            sel = input(f"\n{C_BOLD}➔ أدخل رقم أو اسم مساحة العمل المراد تفعيلها: {C_RESET}").strip()
            target_name = ""
            if sel.isdigit() and 1 <= int(sel) <= len(ws_list):
                target_name = ws_list[int(sel) - 1]
            else:
                target_name = sel
                
            if not target_name or target_name not in workspaces:
                print(f"\n{C_RED}❌ مساحة العمل غير موجودة.{C_RESET}")
                time.sleep(1.5)
                return
                
            sel_res = requests.post(f"{API_URL}/api/workspace/select", json={"name": target_name}, timeout=3)
            if sel_res.status_code == 200:
                print(f"\n{C_GREEN}✅ تم تبديل وتفعيل مساحة العمل [{target_name}] بنجاح!{C_RESET}")
            else:
                print(f"\n{C_RED}❌ فشل التبديل: {sel_res.text}{C_RESET}")
            time.sleep(1.5)
            
        elif sub_choice == 'a':
            name = input(f"\n{C_BOLD}➔ أدخل اسم مساحة العمل الجديدة بالإنجليزية (أرقام وحروف وعلامة _ فقط): {C_RESET}").strip()
            if not name:
                return
            mode = input(f"{C_BOLD}➔ حدد وضع الحماية والصرامة ({C_CYAN}active{C_RESET} / {C_PINK}strict{C_RESET}) [الافتراضي: active]: {C_RESET}").strip().lower()
            if mode not in ["active", "strict"]:
                mode = "active"
                
            add_res = requests.post(f"{API_URL}/api/workspace/add", json={"name": name, "mode": mode}, timeout=3)
            if add_res.status_code == 200:
                print(f"\n{C_GREEN}✅ تم إنشاء مساحة العمل الجديدة [{name}] بنجاح!{C_RESET}")
            else:
                print(f"\n{C_RED}❌ فشل إنشاء مساحة العمل: {add_res.text}{C_RESET}")
            time.sleep(1.5)
            
        elif sub_choice == 'd':
            sel = input(f"\n{C_BOLD}➔ أدخل رقم أو اسم مساحة العمل المراد حذفها: {C_RESET}").strip()
            target_name = ""
            if sel.isdigit() and 1 <= int(sel) <= len(ws_list):
                target_name = ws_list[int(sel) - 1]
            else:
                target_name = sel
                
            if not target_name or target_name not in workspaces:
                print(f"\n{C_RED}❌ مساحة العمل غير موجودة.{C_RESET}")
                time.sleep(1.5)
                return
                
            if target_name == "العقل العام (الافتراضي)":
                print(f"\n{C_RED}❌ لا يمكن حذف مساحة العمل الافتراضية العقل العام!{C_RESET}")
                time.sleep(2)
                return
                
            confirm = input(f"{C_RED}{C_BOLD}⚠️ تحذير: سيتم حذف كافة مفاهيم وعلاقات مساحة العمل [{target_name}] نهائياً من القرص. اكتب 'yes' للتأكيد: {C_RESET}").strip().lower()
            if confirm == 'yes':
                del_res = requests.post(f"{API_URL}/api/workspace/delete", json={"name": target_name}, timeout=3)
                if del_res.status_code == 200:
                    print(f"\n{C_GREEN}✅ تم حذف مساحة العمل وإزالة قاعدة بياناتها نهائياً!{C_RESET}")
                else:
                    print(f"\n{C_RED}❌ فشل الحذف: {del_res.text}{C_RESET}")
                time.sleep(1.5)
                
    except Exception as e:
        print(f"\n{C_RED}❌ خطأ في الاتصال بالخادم: {str(e)}{C_RESET}")
        time.sleep(2)

def main():
    global active_lang
    
    # Default to English at startup. Users can change language using [L] in the menu.
    active_lang = "en"
    
    while True:
        clear_terminal()
        show_banner()
        
        # Check server status
        server_online = check_server()
        status_str = f"{C_GREEN}● ONLINE ({t('online')}){C_RESET}" if server_online else f"{C_RED}● OFFLINE ({t('offline')}){C_RESET}"
        
        print(f" {C_BOLD}{t('server_status')}:{C_RESET} {status_str}")
        print(f" {C_BOLD}{t('active_provider')}:{C_RESET} {C_CYAN}{config['provider']}{C_RESET} ➔ {C_PURPLE}{config['model']}{C_RESET}")
        print("-" * 82)
        
        print(f"  {C_GOLD}{C_BOLD}[1]{C_RESET} 📖 {C_BOLD}{t('menu_doc')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[2]{C_RESET} 🎓 {C_BOLD}{t('menu_teach')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[3]{C_RESET} 🔍 {C_BOLD}{t('menu_query')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[4]{C_RESET} 📊 {C_BOLD}{t('menu_stats')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[5]{C_RESET} 💤 {C_BOLD}{t('menu_sleep')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[6]{C_RESET} 🧬 {C_BOLD}{t('menu_evolve')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[7]{C_RESET} ✨ {C_BOLD}{t('menu_induct')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[8]{C_RESET} 💭 {C_BOLD}{t('menu_socratic')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[9]{C_RESET} 🔬 {C_BOLD}{t('menu_sandbox')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[10]{C_RESET} 🗑️ {C_BOLD}{t('menu_delete')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[11]{C_RESET} 🧩 {C_BOLD}{t('menu_rules')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[12]{C_RESET} 📥 {C_BOLD}{t('menu_export')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[13]{C_RESET} 📤 {C_BOLD}{t('menu_import')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[0]{C_RESET} ❌ {C_BOLD}{t('menu_clear')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[C]{C_RESET} ⚙️ {C_BOLD}{t('menu_config')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[W]{C_RESET} 💼 {C_BOLD}{t('menu_workspace')}{C_RESET}")
        print(f"  {C_GOLD}{C_BOLD}[L]{C_RESET} 🌐 {C_BOLD}{t('menu_lang')}{C_RESET}")
        print(f"  {C_RED}{C_BOLD}[Q]{C_RESET} 🚪 {C_BOLD}{t('menu_exit')}{C_RESET}")
        print("-" * 82)
        
        choice = input(f"{C_BOLD}➔ {t('menu_title')} {C_RESET}").strip()
        
        if choice.lower() == 'q':
            clear_terminal()
            print(f"\n{C_GREEN}{t('exit_msg')}{C_RESET}\n")
            break
            
        if choice.lower() == 'l':
            clear_terminal()
            show_banner()
            print(f"\n{C_CYAN}{C_BOLD}{t('lang_switch_title')}{C_RESET}")
            new_lang = input(t('lang_switch_prompt')).strip().lower()
            if new_lang in translations:
                active_lang = new_lang
                print(f"\n{C_GREEN}{t('lang_switch_success')}{C_RESET}")
            else:
                print(f"\n{C_RED}⚠️ Unsupported language code / لغة غير مدعومة{C_RESET}")
            time.sleep(1.5)
            continue
            
        if choice.lower() == 'c':
            config["api_key"] = ""
            load_or_prompt_config()
            print(f"\n{C_GREEN}✅ Configuration updated successfully!{C_RESET}")
            time.sleep(1.5)
            continue
            
        if not server_online and choice.lower() in ['2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '0', 'w']:
            print(f"\n{C_RED}⚠️ {t('offline')}{C_RESET}")
            time.sleep(2)
            continue
            
        if choice == '1':
            show_documentation()
        elif choice == '2':
            interactive_teach()
        elif choice == '3':
            interactive_query()
        elif choice == '4':
            view_live_metrics()
        elif choice == '5':
            run_cognitive_operation("/api/sleep", t('menu_sleep'))
        elif choice == '6':
            run_cognitive_operation("/api/rules/evolve", t('menu_evolve'))
        elif choice == '7':
            run_cognitive_operation("/api/rules/induct", t('menu_induct'))
        elif choice == '8':
            run_socratic_lab()
        elif choice == '9':
            run_thought_sandbox_lab()
        elif choice == '10':
            interactive_delete_element()
        elif choice == '11':
            interactive_rules_governance()
        elif choice == '12':
            interactive_export_workspace()
        elif choice == '13':
            interactive_import_workspace()
        elif choice.lower() == 'w':
            interactive_workspaces_governance()
        elif choice == '0':
            wipe_knowledge()
        else:
            print(f"\n{C_RED}{t('invalid_selection')}{C_RESET}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear_terminal()
        print(f"\n{C_GREEN}🪐 شكراً لاستخدامك نظام LEGEND الاستدلالي. وداعاً!{C_RESET}\n")
        sys.exit(0)
