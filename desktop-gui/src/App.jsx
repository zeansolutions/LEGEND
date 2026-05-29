import React, { useState, useEffect, useRef } from 'react';
import { 
  Network, Database, BrainCircuit, Shield, AlertTriangle, Play, HelpCircle, 
  Trash2, Plus, Sparkles, BookOpen, Layers, CheckCircle2, RefreshCw, Moon, Eye, EyeOff,
  Copy, BarChart2, Activity, Download, Upload, XCircle
} from 'lucide-react';
import PhysicsGraph from './PhysicsGraph';
import { translations, supportedLanguages } from './translations';
import { localTranslations } from './localTranslations';

// Merge localTranslations into translations globally
Object.keys(localTranslations).forEach(lang => {
  if (translations[lang]) {
    translations[lang] = { ...translations[lang], ...localTranslations[lang] };
  } else {
    translations[lang] = localTranslations[lang];
  }
});


const DEFAULT_KEYS = {
  Google: {
    models: ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemma-4-31b-it"]
  },
  Groq: {
    models: ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]
  },
  OpenRouter: {
    models: ["google/gemini-2.5-flash", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"]
  }
};

const App = () => {
  // Language & Internationalization State
  const [language, setLanguage] = useState(() => localStorage.getItem('legend_language') || 'ar');

  // Save language settings to localStorage and backend on change
  useEffect(() => {
    localStorage.setItem('legend_language', language);
    const saveSettings = async () => {
      try {
        await fetch('http://127.0.0.1:8000/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language })
        });
      } catch (err) {
        console.error("Failed to save settings to backend:", err);
      }
    };
    saveSettings();
  }, [language]);

  // Translation helper function supporting dynamic token variable interpolation
  const t = (key, variables = {}) => {
    const langDict = translations[language] || translations['en'];
    let text = langDict[key] || translations['en'][key] || key;
    if (typeof text === 'string') {
      Object.keys(variables).forEach(varName => {
        text = text.replace(new RegExp(`{${varName}}`, 'g'), variables[varName]);
      });
    }
    return text;
  };

  // Config & API parameters
  const [provider, setProvider] = useState('Google');
  const [model, setModel] = useState('gemini-2.5-flash');
  const [sentence, setSentence] = useState('');
  
  // Custom API keys management map
  const [apiKeys, setApiKeys] = useState({
    Google: '',
    Groq: '',
    OpenRouter: ''
  });

  // Premium Promise-based Custom Modal Dialog State
  const [customModal, setCustomModal] = useState({
    isOpen: false,
    title: '',
    message: '',
    type: 'confirm', // 'confirm' or 'alert'
    isDestructive: false,
    confirmLabel: '',
    cancelLabel: '',
    resolve: null
  });

  const showConfirm = (message, title = '', isDestructive = false) => {
    return new Promise((resolve) => {
      setCustomModal({
        isOpen: true,
        title: title || t('confirmTitle'),
        message,
        type: 'confirm',
        isDestructive,
        confirmLabel: language === 'ar' ? 'تأكيد' : 'Confirm',
        cancelLabel: language === 'ar' ? 'إلغاء' : 'Cancel',
        resolve
      });
    });
  };

  const showAlert = (message, title = '') => {
    return new Promise((resolve) => {
      setCustomModal({
        isOpen: true,
        title: title || t('alertTitle'),
        message,
        type: 'alert',
        isDestructive: false,
        confirmLabel: language === 'ar' ? 'موافق' : 'OK',
        cancelLabel: '',
        resolve
      });
    });
  };

  const handleModalConfirm = () => {
    if (customModal.resolve) {
      customModal.resolve(true);
    }
    setCustomModal(prev => ({ ...prev, isOpen: false, resolve: null }));
  };

  const handleModalCancel = () => {
    if (customModal.resolve) {
      customModal.resolve(false);
    }
    setCustomModal(prev => ({ ...prev, isOpen: false, resolve: null }));
  };
  
  // Dynamic OpenRouter models list loaded at runtime categorized by pricing
  const [openRouterModels, setOpenRouterModels] = useState({
    free: [
      { id: "google/gemini-2.5-flash", name: "Google: Gemini 2.5 Flash" },
      { id: "deepseek/deepseek-chat", name: "DeepSeek: DeepSeek Chat" },
      { id: "meta-llama/llama-3.3-70b-instruct", name: "Meta: LLaMA 3.3 70B Instruct" }
    ],
    paid: [
      { id: "deepseek/deepseek-r1", name: "DeepSeek: DeepSeek R1" },
      { id: "anthropic/claude-3.5-sonnet", name: "Anthropic: Claude 3.5 Sonnet" },
      { id: "openai/gpt-4o-mini", name: "OpenAI: GPT-4o Mini" }
    ]
  });
  const [localModels, setLocalModels] = useState([]);

  // Derived active key to keep all backend fetch bodies seamlessly integrated
  const apiKey = apiKeys[provider] || '';
  
  // App States
  const [workspaces, setWorkspaces] = useState({});
  const [currentWorkspace, setCurrentWorkspace] = useState('');
  const [workspaceMode, setWorkspaceMode] = useState('active');
  const [isWorkspaceModalOpen, setIsWorkspaceModalOpen] = useState(false);
  const [newWsName, setNewWsName] = useState('');
  const [newWsMode, setNewWsMode] = useState('active');
  
  // Graph & Database
  const [graphData, setGraphData] = useState({ nodes: [], edges: [], in_sandbox: false });
  const [activeNode, setActiveNode] = useState(null);
  const [rules, setRules] = useState([]);
  
  // Semantic relationships list
  const [relationsSearch, setRelationsSearch] = useState('');
  const [relationsPage, setRelationsPage] = useState(1);
  const relationsPerPage = 8;
  
  // Logs & Response
  const [logs, setLogs] = useState([
    { type: 'info', text: '...' }
  ]);
  const [response, setResponse] = useState('');
  const [parsedData, setParsedData] = useState(null);
  const [contradictions, setContradictions] = useState([]);
  
  // Sleep & Curiosity states
  const [sleepLogs, setSleepLogs] = useState('');
  const [isSleeping, setIsSleeping] = useState(false);
  const [curiosityQuestions, setCuriosityQuestions] = useState([]);
  const [isCuriosityLoading, setIsCuriosityLoading] = useState(false);
  
  // PLN form
  const [plnConceptA, setPlnConceptA] = useState('');
  const [plnConceptB, setPlnConceptB] = useState('');
  const [plnResult, setPlnResult] = useState('');
  const [plnLogs, setPlnLogs] = useState([]);
  const [isPlnLoading, setIsPlnLoading] = useState(false);
  
  // Sandbox status
  const [inSandbox, setInSandbox] = useState(false);
  
  // UI Tabs: 'cognitive', 'database', 'sleep', 'rules', 'sandbox', 'stats', 'advanced', 'documentation'
  const [activeTab, setActiveTab] = useState('cognitive');
  const [isWorking, setIsWorking] = useState(false);

  // Advanced Cognitive Features State
  const [metacognition, setMetacognition] = useState(null);
  const [isMetaLoading, setIsMetaLoading] = useState(false);
  
  const [hypothesis, setHypothesis] = useState('');
  const [thoughtExpLogs, setThoughtExpLogs] = useState([]);
  const [thoughtExpEdges, setThoughtExpEdges] = useState([]);
  const [thoughtExpContradictions, setThoughtExpContradictions] = useState([]);
  const [isThoughtExpLoading, setIsThoughtExpLoading] = useState(false);
  
  const [newRuleName, setNewRuleName] = useState('');
  const [newRuleConfidence, setNewRuleConfidence] = useState(1.0);
  const [newRuleAntecedents, setNewRuleAntecedents] = useState('?x, مساهم_في, ?y\n?y, تخضع_لـ, قانون الاستثمار الجديد');
  const [newRuleConsequent, setNewRuleConsequent] = useState('?x, له_حصانة_ضد, الحجز المباشر');
  const [showAddRuleForm, setShowAddRuleForm] = useState(false);
  
  const [socraticDialogue, setSocraticDialogue] = useState('');
  const [socraticDecision, setSocraticDecision] = useState('');
  const [socraticBelief, setSocraticBelief] = useState('');
  const [socraticLogs, setSocraticLogs] = useState([]);
  const [isSocraticLoading, setIsSocraticLoading] = useState(false);
  
  const [passiveText, setPassiveText] = useState('');
  const [passiveLogs, setPassiveLogs] = useState([]);
  const [passiveAbsorbed, setPassiveAbsorbed] = useState(0);
  const [passiveContradictions, setPassiveContradictions] = useState(0);
  const [isPassiveLoading, setIsPassiveLoading] = useState(false);
  
  const [diffWorkspaceName, setDiffWorkspaceName] = useState('');
  const [workspaceDiff, setWorkspaceDiff] = useState(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);
  
  const [newProcedureName, setNewProcedureName] = useState('');
  const [newProcedureSteps, setNewProcedureSteps] = useState('');
  const [procedures, setProcedures] = useState({});
  const [isProceduralLoading, setIsProceduralLoading] = useState(false);
  const [isProcedureGlobal, setIsProcedureGlobal] = useState(false);
  
  const [federatedQuery, setFederatedQuery] = useState('');
  const [federatedPeer, setFederatedPeer] = useState('');
  const [federatedConcepts, setFederatedConcepts] = useState([]);
  const [federatedTriples, setFederatedTriples] = useState([]);
  const [federatedLogs, setFederatedLogs] = useState([]);
  const [isFederatedLoading, setIsFederatedLoading] = useState(false);

  const [geneticLogs, setGeneticLogs] = useState([]);
  const [geneticCount, setGeneticCount] = useState(0);
  const [isGeneticLoading, setIsGeneticLoading] = useState(false);

  // Panel Resizing Height state
  const [graphHeight, setGraphHeight] = useState(400);
  const [showPhysicsGraph, setShowPhysicsGraph] = useState(true);
  const isDragging = useRef(false);

  // Statistics State
  const [stats, setStats] = useState(null);
  const [isStatsLoading, setIsStatsLoading] = useState(false);

  const fetchStats = async () => {
    setIsStatsLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/stats');
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error("Failed to fetch statistics:", err);
    } finally {
      setIsStatsLoading(false);
    }
  };

  const startDrag = (e) => {
    isDragging.current = true;
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', stopDrag);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  };

  const onDrag = (e) => {
    if (!isDragging.current) return;
    const mainElement = document.querySelector('main');
    if (mainElement) {
      const rect = mainElement.getBoundingClientRect();
      const newHeight = e.clientY - rect.top;
      if (newHeight >= 200 && newHeight <= 750) {
        setGraphHeight(newHeight);
      }
    }
  };

  const stopDrag = () => {
    isDragging.current = false;
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', stopDrag);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  };
  
  const logEndRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const [currentProgress, setCurrentProgress] = useState(null);

  // Poll progress state
  useEffect(() => {
    let interval = null;
    const isAnyLoading = isWorking || isPassiveLoading || isSocraticLoading || isCuriosityLoading;
    
    if (isAnyLoading) {
      interval = setInterval(async () => {
        try {
          const res = await fetch('http://127.0.0.1:8000/api/status/current');
          const data = await res.json();
          if (data && data.active) {
            setCurrentProgress(data);
          } else {
            setCurrentProgress(null);
          }
        } catch (err) {
          console.error("Error polling status:", err);
        }
      }, 400);
    } else {
      setCurrentProgress(null);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isWorking, isPassiveLoading, isSocraticLoading, isCuriosityLoading]);

  // Initial Data Fetching & Dynamic Models Loading
  useEffect(() => {
    fetchWorkspaces();
    
    // 1. Load provider
    const savedProvider = localStorage.getItem('legend_llm_provider') || 'Google';
    setProvider(savedProvider);
    
    // 2. Load keys map
    const savedKeys = localStorage.getItem('legend_api_keys');
    let loadedKeys = { Google: '', Groq: '', OpenRouter: '' };
    if (savedKeys) {
      try {
        loadedKeys = JSON.parse(savedKeys);
      } catch (e) {}
    }
    setApiKeys(loadedKeys);
    
    // 3. Fetch OpenRouter Models dynamically
    const fetchOpenRouterModels = async () => {
      try {
        const res = await fetch('https://openrouter.ai/api/v1/models');
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.data)) {
            const freeList = [];
            const paidList = [];
            data.data.forEach(m => {
              const isFree = m.pricing && 
                             parseFloat(m.pricing.prompt) === 0 && 
                             parseFloat(m.pricing.completion) === 0;
              const modelInfo = {
                id: m.id,
                name: m.name || m.id
              };
              if (isFree) {
                freeList.push(modelInfo);
              } else {
                paidList.push(modelInfo);
              }
            });
            // Sort lists alphabetically by name
            freeList.sort((a, b) => a.name.localeCompare(b.name));
            paidList.sort((a, b) => a.name.localeCompare(b.name));
            setOpenRouterModels({ free: freeList, paid: paidList });
          }
        }
      } catch (err) {
        console.error("Failed to fetch dynamic OpenRouter models:", err);
      }
    };
    fetchOpenRouterModels();
    
    const fetchLocalModels = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/local_models');
        if (res.ok) {
          const data = await res.json();
          if (data && data.models) setLocalModels(data.models);
        }
      } catch (e) {
        console.error("Failed to load local models", e);
      }
    };
    fetchLocalModels();

    // 4. Load model
    const savedModel = localStorage.getItem('legend_llm_model');
    if (savedModel) {
      setModel(savedModel);
    } else {
      setModel(savedProvider === 'OpenRouter' ? 'google/gemini-2.5-flash' : DEFAULT_KEYS[savedProvider]?.models[0] || '');
    }
  }, []);

  // Save config to local storage
  useEffect(() => {
    localStorage.setItem('legend_llm_provider', provider);
    localStorage.setItem('legend_llm_model', model);
    localStorage.setItem('legend_api_keys', JSON.stringify(apiKeys));
  }, [provider, model, apiKeys]);

  const handleProviderChange = async (selected) => {
    setProvider(selected);
    let defaultModel;
    
    if (selected === 'Local') {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/local_models');
        if (res.ok) {
          const data = await res.json();
          if (data && data.models) {
            setLocalModels(data.models);
            defaultModel = data.models[0] || '';
          }
        }
      } catch (e) {
        console.error("Failed to load local models", e);
      }
    } else if (selected === 'OpenRouter') {
      defaultModel = openRouterModels.free.length > 0 ? openRouterModels.free[0].id : (openRouterModels.paid[0]?.id || '');
    } else {
      defaultModel = DEFAULT_KEYS[selected]?.models[0];
    }
    
    if (defaultModel) {
      setModel(defaultModel);
    }
    addLog(t('changeWsSuccess', { selected }), 'info');
  };

  // Fetch workspaces list with automatic retry to handle backend server startup delay
  const fetchWorkspaces = async (retries = 6, delay = 500) => {
    for (let i = 0; i < retries; i++) {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/workspaces');
        const data = await res.json();
        setWorkspaces(data);
        const wsKeys = Object.keys(data);
        if (wsKeys.length > 0 && !currentWorkspace) {
          selectWorkspace(wsKeys[0]);
        }
        return; // Success, exit
      } catch (err) {
        if (i === retries - 1) {
          addLog(t('backendConnError'), 'warn');
        } else {
          // Wait and try again
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }
  };

  // Select Workspace
  const selectWorkspace = async (name) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/workspace/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setCurrentWorkspace(name);
        setWorkspaceMode(data.mode);
        addLog(t('wsLoadSuccess', { name: name === 'العقل العام (الافتراضي)' ? t('defaultWorkspaceName') : name, mode: data.mode === 'active' ? t('wsModeActiveText') : t('wsModeStrictText') }), 'success');
        fetchGraph();
        fetchRules();
        fetchCuriosity();
      }
    } catch (err) {
      addLog(t('wsSwitchFail'), 'warn');
    }
  };

  // Fetch Graph
  const fetchGraph = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/graph?t=${Date.now()}`);
      const data = await res.json();
      setGraphData(data);
      setInSandbox(data.in_sandbox);
    } catch (err) {
      console.error('Failed to fetch graph data:', err);
    }
  };

  // Fetch Rules
  const fetchRules = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/rules?t=${Date.now()}`);
      const data = await res.json();
      setRules(data);
    } catch (err) {
      console.error('Failed to fetch rules:', err);
    }
  };

  // Add Custom Rule manually
  const handleAddRule = async (e) => {
    e.preventDefault();
    if (!newRuleName.trim()) {
      addLog(t('ruleNameUniqueError'), 'error');
      return;
    }
    
    // Parse antecedents
    const lines = newRuleAntecedents.split('\n').map(l => l.trim()).filter(Boolean);
    const parsedAntecedents = [];
    for (const line of lines) {
      const parts = line.split(',').map(p => p.trim());
      if (parts.length < 3) {
        addLog(t('ruleSyntaxConditionError', { line }), 'error');
        return;
      }
      parsedAntecedents.push([parts[0], parts[1], parts[2]]);
    }
    
    // Parse consequent
    const consParts = newRuleConsequent.split(',').map(p => p.trim());
    if (consParts.length < 3) {
      addLog(t('ruleSyntaxConsequentError'), 'error');
      return;
    }
    const parsedConsequent = [consParts[0], consParts[1], consParts[2]];
    
    try {
      addLog(t('ruleInsertingText'), 'process');
      const res = await fetch('http://127.0.0.1:8000/api/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rule_name: newRuleName.trim(),
          antecedents: parsedAntecedents,
          consequent: parsedConsequent,
          confidence: parseFloat(newRuleConfidence)
        })
      });
      const data = await res.json();
      if (res.ok) {
        addLog(data.message || t('ruleAddSuccess'), 'success');
        setNewRuleName('');
        fetchRules();
        setShowAddRuleForm(false);
      } else {
        addLog(t('ruleAddFail', { error: data.detail || data.message }), 'error');
      }
    } catch (err) {
      console.error(err);
      addLog(t('ruleAddErrorUnexpected'), 'error');
    }
  };

  // Delete specific logical rule
  const handleDeleteRule = async (ruleName) => {
    const confirmed = await showConfirm(t('ruleDeleteConfirm', { ruleName }), null, true);
    if (!confirmed) return;
    try {
      addLog(t('ruleDeletingText', { ruleName }), 'process');
      const res = await fetch(`http://127.0.0.1:8000/api/rules/${encodeURIComponent(ruleName)}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (res.ok) {
        addLog(data.message || t('ruleDeleteSuccess'), 'success');
        fetchRules();
      } else {
        addLog(t('ruleDeleteFail', { error: data.detail || data.message }), 'error');
      }
    } catch (err) {
      console.error(err);
      addLog(t('ruleDeleteErrorUnexpected'), 'error');
    }
  };

  // Fetch active curiosity questions
  const fetchCuriosity = async () => {
    if (workspaceMode === 'strict') {
      setCuriosityQuestions([]);
      return;
    }
    setIsCuriosityLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/curiosity?t=${Date.now()}`);
      const data = await res.json();
      setCuriosityQuestions(data.questions || []);
    } catch (err) {
      console.error('Failed to fetch curiosity:', err);
    } finally {
      setIsCuriosityLoading(false);
    }
  };

  // Create Workspace
  const handleCreateWorkspace = async (e) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    try {
      const res = await fetch('http://127.0.0.1:8000/api/workspace/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newWsName, mode: newWsMode })
      });
      const data = await res.json();
      if (res.ok) {
        setIsWorkspaceModalOpen(false);
        setNewWsName('');
        await fetchWorkspaces();
        selectWorkspace(newWsName);
      } else {
        await showAlert(data.detail || t('wsCreateFail'));
      }
    } catch (err) {
      await showAlert(t('wsServerError'));
    }
  };

  // Delete current workspace
  const handleDeleteWorkspace = async () => {
    if (currentWorkspace === 'العقل العام (الافتراضي)') {
      await showAlert(t('wsDeleteDefaultError'));
      return;
    }
    const confirmed = await showConfirm(t('wsDeleteConfirm', { name: currentWorkspace === 'العقل العام (الافتراضي)' ? t('defaultWorkspaceName') : currentWorkspace }), null, true);
    if (!confirmed) {
      return;
    }
    try {
      const res = await fetch('http://127.0.0.1:8000/api/workspace/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: currentWorkspace })
      });
      if (res.ok) {
        setCurrentWorkspace('');
        await fetchWorkspaces();
      }
    } catch (err) {
      await showAlert(t('wsDeleteError'));
    }
  };

  // Export Workspace to JSON
  const handleExportWorkspace = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/workspace/export?name=${encodeURIComponent(currentWorkspace)}`);
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const downloadAnchor = document.createElement('a');
        downloadAnchor.href = url;
        
        const cleanName = currentWorkspace.replace(/[^a-zA-Z0-9_\u0600-\u06FF]/g, '_');
        downloadAnchor.download = `${cleanName}_workspace.json`;
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
        URL.revokeObjectURL(url);
      } else {
        const errText = await res.text();
        await showAlert(t('wsExportError', { error: errText }));
      }
    } catch (err) {
      await showAlert(t('wsExportError', { error: err.message }));
    }
  };

  // Import Workspace from JSON
  const handleImportWorkspace = () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.json';
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      const reader = new FileReader();
      reader.onload = async (evt) => {
        try {
          const payload = JSON.parse(evt.target.result);
          
          if (!payload.workspace_name || !payload.concepts || !payload.triples || !payload.rules) {
            await showAlert("Invalid workspace JSON structure. Missing required properties (workspace_name, concepts, triples, rules).");
            return;
          }
          
          const confirmed = await showConfirm(
            t('wsImportConfirm', { name: payload.workspace_name }) || `Importing workspace will overwrite database tables. Are you sure you want to import workspace '${payload.workspace_name}'?`,
            null,
            false
          );
          if (!confirmed) return;
          
          const res = await fetch('http://127.0.0.1:8000/api/workspace/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          
          if (res.ok) {
            await showAlert(t('wsImportSuccess', { name: payload.workspace_name }));
            setCurrentWorkspace(payload.workspace_name);
            await fetchWorkspaces();
          } else {
            const errText = await res.text();
            await showAlert(t('wsImportError', { error: errText }));
          }
        } catch (err) {
          await showAlert(t('wsImportError', { error: err.message }));
        }
      };
      reader.readAsText(file);
    };
    fileInput.click();
  };

  // Clear Database (تصفير العقل)
  const handleClearDatabase = async () => {
    const confirmed = await showConfirm(t('dbClearConfirm'), null, true);
    if (!confirmed) {
      return;
    }
    try {
      const res = await fetch('http://127.0.0.1:8000/api/clear', { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        addLog(t('dbClearSuccess'), "warn");
        fetchGraph();
        fetchRules();
        fetchProcedures();
        if (activeTab === 'stats') {
          fetchStats();
        }
      } else {
        await showAlert(t('dbClearFail'));
      }
    } catch (err) {
      await showAlert(t('dbClearErrorUnexpected'));
    }
  };

  // Delete specific relation (حذف علاقة معينة)
  const handleDeleteRelation = async (source, relation, target) => {
    const confirmed = await showConfirm(t('relationDeleteConfirm', { source, target, relation }), null, true);
    if (!confirmed) {
      return;
    }
    try {
      const res = await fetch('http://127.0.0.1:8000/api/relation/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, relation, target })
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        addLog(t('relationDeleteSuccess', { source, relation, target }), 'warn');
        fetchGraph();
        if (activeTab === 'stats') {
          fetchStats();
        }
      } else {
        await showAlert(t('relationDeleteFail'));
      }
    } catch (err) {
      await showAlert(t('relationDeleteServerError'));
    }
  };

  // Delete specific node (حذف كيان/مفهوم بالكامل)
  const handleDeleteNode = async (nodeName) => {
    if (!nodeName) return;
    const confirmed = await showConfirm(t('nodeDeleteConfirm', { nodeName }), null, true);
    if (!confirmed) {
      return;
    }
    try {
      const res = await fetch('http://127.0.0.1:8000/api/node/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nodeName })
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        addLog(t('nodeDeleteSuccess', { nodeName }), 'warn');
        setActiveNode(null);
        setSentence('');
        fetchGraph();
        if (activeTab === 'stats') {
          fetchStats();
        }
      } else {
        await showAlert(t('nodeDeleteFail'));
      }
    } catch (err) {
      await showAlert(t('nodeDeleteServerError'));
    }
  };

  const translateLogText = (text) => {
    if (!text) return text;
    
    // 1. Google API Connection
    if (text.includes("جاري الاتصال بـ Google API بالنموذج")) {
      const modelMatch = text.match(/بالنموذج:\s*([^\s(]+)/);
      const model = modelMatch ? modelMatch[1] : "";
      const attemptMatch = text.match(/محاولة\s*(\d+)/);
      const attempt = attemptMatch ? attemptMatch[1] : "1";
      return t("logGoogleApiConnect", { model, attempt });
    }

    // 2. Generic API Connection
    if (text.includes("جاري الاتصال بـ") && text.includes("بالنموذج")) {
      const providerMatch = text.match(/جاري الاتصال بـ\s*([^\s]+)/);
      const provider = providerMatch ? providerMatch[1] : "";
      const modelMatch = text.match(/بالنموذج:\s*([^\s(]+)/);
      const model = modelMatch ? modelMatch[1] : "";
      const attemptMatch = text.match(/محاولة\s*(\d+)/);
      const attempt = attemptMatch ? attemptMatch[1] : "1";
      return t("logGenericApiConnect", { provider, model, attempt });
    }

    // 3. Attempt Failed
    if (text.includes("المحاولة") && text.includes("فشلت")) {
      const attemptMatch = text.match(/المحاولة\s*(\d+)/);
      const attempt = attemptMatch ? attemptMatch[1] : "1";
      const error = text.split("فشلت:")[1] || "";
      return t("logAttemptFailed", { attempt, error });
    }

    // 4. Alternative Choice
    if (text.includes("محاولة بديلة أولى") && text.includes("الشقيق")) {
      const modelMatch = text.match(/الشقيق:\s*([^\s.]+)/);
      const model = modelMatch ? modelMatch[1] : "";
      return t("logGemmaAlternative", { model });
    }

    // 5. Alternate Failed
    if (text.includes("الشقيق") && text.includes("لم يستجب أيضاً")) {
      const modelMatch = text.match(/الشقيق\s*([^\s]+)/);
      const model = modelMatch ? modelMatch[1] : "";
      const error = text.split("أيضاً:")[1] || "";
      return t("logGemmaFailed", { model, error });
    }

    // 6. Final Fallback
    if (text.includes("محاولة أخيرة بديلة") && text.includes("المستقر")) {
      const modelMatch = text.match(/المستقر\s*([^\s.]+)/);
      const model = modelMatch ? modelMatch[1] : "";
      return t("logFinalFallback", { model });
    }

    // 7. Strict mode learning block
    if (text.includes("وضع الحقائق الثابتة") && text.includes("تم إيقاف الاستدلال التلقائي")) {
      return t("logStrictModeLearnDisabled");
    }

    // 8. Category Inheritance
    if (text.includes("استدلال دلالي ذاتي") && text.includes("وراثة فئوية جديدة")) {
      const parts = text.match(/\((.*?)\s*➔\s*is_a\s*➔\s*(.*?)\)/);
      const node = parts ? parts[1] : "";
      const ancestor = parts ? parts[2] : "";
      return t("logCategoryInheritance", { node, ancestor });
    }

    // 9. Load rules fail
    if (text.includes("تعذر تحميل القواعد النشطة")) {
      const error = text.split("قاعدة البيانات:")[1] || "";
      return t("logLoadRulesFail", { error });
    }

    // 10. Rule parse error
    if (text.includes("خطأ في قراءة صيغة القاعدة")) {
      const nameMatch = text.match(/القاعدة\s*([^\s:]+)/);
      const name = nameMatch ? nameMatch[1] : "";
      const error = text.split(":")[1] || "";
      return t("logRuleParseFail", { name, error });
    }

    // 11. Hybrid inference start
    if (text.includes("محرك الاستدلال الهجين") && text.includes("بدء تشغيل حلقة الاستدلال")) {
      return t("logHybridInferenceStart");
    }

    // 12. Inference iteration results
    if (text.includes("التكرار رقم") && text.includes("روابط جديدة")) {
      const iterMatch = text.match(/رقم\s*(\d+)/);
      const iteration = iterMatch ? iterMatch[1] : "1";
      const countMatch = text.match(/باستنتاج\s*(\d+)/);
      const count = countMatch ? countMatch[1] : "0";
      return t("logIterationFinished", { iteration, count });
    }

    // 13. Infinite loop safeguard
    if (text.includes("تم إيقاف حلقة الاستدلال للوصول للحد الأقصى")) {
      return t("logInfiniteLoopSafeguard");
    }

    // 14. Hybrid inference settled
    if (text.includes("استقر محرك الاستدلال بنجاح بعد")) {
      const iterMatch = text.match(/بعد\s*(\d+)/);
      const iteration = iterMatch ? iterMatch[1] : "1";
      return t("logHybridInferenceSettled", { iteration });
    }

    // 15. Contradiction detected
    if (text.includes("كاشف التناقض المنطقي") && text.includes("تم اكتشاف تعارض")) {
      return t("logContradictionDetectedTitle");
    }
    if (text.includes("سيقوم النظام بتسجيل المعلومات مع الاحتفاظ بالتحذير")) {
      return t("logContradictionWarningKeep");
    }

    // 16. New concept absorbed
    if (text.includes("إدراج مفهوم جديد")) {
      const parts = text.match(/'(.*?)'\s*➔\s*تصنيفه:\s*'(.*?)'\s*بـثقة\s*([\d.]+)/);
      const name = parts ? parts[1] : "";
      const ent_type = parts ? parts[2] : "";
      const conf = parts ? parts[3] : "1.0";
      return t("logNewConceptAbsorbed", { name, type: ent_type, conf });
    }

    // 17. Fuzzy logic adjusting confidence
    if (text.includes("تعديل ثقة العلاقة") && text.includes("مؤشر احتمالي")) {
      const parts = text.match(/\((.*?)\s*➔\s*(.*?)\s*➔\s*(.*?)\)\s*لـ\s*([\d.]+)/);
      const subj = parts ? parts[1] : "";
      const pred = parts ? parts[2] : "";
      const obj = parts ? parts[3] : "";
      const conf = parts ? parts[4] : "1.0";
      return t("logFuzzyProbabilistic", { subj, pred, obj, conf });
    }
    if (text.includes("رفع ثقة العلاقة") && text.includes("مؤشر يقيني")) {
      const parts = text.match(/\((.*?)\s*➔\s*(.*?)\s*➔\s*(.*?)\)\s*لـ\s*([\d.]+)/);
      const subj = parts ? parts[1] : "";
      const pred = parts ? parts[2] : "";
      const obj = parts ? parts[3] : "";
      const conf = parts ? parts[4] : "1.0";
      return t("logFuzzyCertain", { subj, pred, obj, conf });
    }
    if (text.includes("خفض ثقة العلاقة") && text.includes("مؤشر ندرة")) {
      const parts = text.match(/\((.*?)\s*➔\s*(.*?)\s*➔\s*(.*?)\)\s*لـ\s*([\d.]+)/);
      const subj = parts ? parts[1] : "";
      const pred = parts ? parts[2] : "";
      const obj = parts ? parts[3] : "";
      const conf = parts ? parts[4] : "1.0";
      return t("logFuzzyRare", { subj, pred, obj, conf });
    }

    // 18. Emotional charge
    if (text.includes("ذاكرة انفعالية") && text.includes("شحنة عاطفية")) {
      const valenceMatch = text.match(/valence\s*=\s*([\d.-]+)/);
      const valence = valenceMatch ? valenceMatch[1] : "0";
      return t("logEmotionalCharge", { valence });
    }

    // 19. New Fact Ingested
    if (text.includes("استيعاب حقيقة جديدة")) {
      const parts = text.match(/\((.*?)\s*➔\s*(.*?)\s*➔\s*(.*?)\)(.*?)\s*بـثقة\s*([\d.]+)/);
      const subj = parts ? parts[1] : "";
      const pred = parts ? parts[2] : "";
      const obj = parts ? parts[3] : "";
      const time_info = parts ? parts[4] : "";
      const conf = parts ? parts[5] : "1.0";
      return t("logNewFactIngested", { subj, pred, obj, time_info, conf });
    }

    // 20. DB Memory Synced
    if (text.includes("مزامنة الذاكرة") && text.includes("تم حفظ كافة المعلومات")) {
      return t("logDbMemorySynced");
    }

    // 21. No new info
    if (text.includes("لم يتم العثور على أي معلومات جديدة")) {
      return t("logNoNewFactsFound");
    }

    // 22. Idioms standard translation
    if (text.includes("فك الكنايات العامية")) {
      return t("logIdiomsTranslationTitle");
    }
    if (text.includes("التعبير العامي") && text.includes("المفهوم المعياري الصريح")) {
      const parts = text.match(/'(.*?)'\s*➔\s*المفهوم المعياري الصريح:\s*'(.*?)'/);
      const key = parts ? parts[1] : "";
      const val = parts ? parts[2] : "";
      return t("logIdiomStandardized", { key, val });
    }

    // 23. Node Ancestry Trace
    if (text.includes("تتبع الوراثة الكيان")) {
      const nodeMatch = text.match(/'(.*?)'/);
      const node = nodeMatch ? nodeMatch[1] : "";
      return t("logNodeAncestryTrace", { node });
    }
    if (text.includes("شجرة النسب المعرفي")) {
      const path = text.split("شجرة النسب المعرفي:")[1] || "";
      return t("logNodeAncestryPath", { path });
    }
    if (text.includes("الصفات والخصائص الموروثة")) {
      const props = text.split("الصفات والخصائص الموروثة:")[1] || "";
      return t("logNodeInheritedProperties", { props });
    }

    // 24. Causal critical deduction examples
    if (text.includes("استنتاج منطقي حاسم") && text.includes("تجاهل")) {
      const parts = text.match(/'(.*?)'\s*قد تجاهل\s*'(.*?)'/);
      const subj = parts ? parts[1] : "";
      const obj = parts ? parts[2] : "";
      return t("logCriticalCausalDeduction", { subj, obj });
    }
    if (text.includes("استنتاج رياضي") && text.includes("يمارس")) {
      const parts = text.match(/'(.*?)'\s*يمارس\s*'(.*?)'/);
      const subj = parts ? parts[1] : "";
      const obj = parts ? parts[2] : "";
      return t("logExerciseCausalDeduction", { subj, obj });
    }

    // 25. Semantic path discovered
    if (text.includes("تم اكتشاف مسار دلالي يربط بين")) {
      const parts = text.match(/'(.*?)'\s*و\s*'(.*?)'\s*عبر\s*(\d+)/);
      const c_a = parts ? parts[1] : "";
      const c_b = parts ? parts[2] : "";
      const hops = parts ? parts[3] : "0";
      return t("logSemanticPathDiscovered", { c_a, c_b, hops });
    }

    // 26. Probabilistic logical strict limit
    if (text.includes("تم إيقاف الاستدلال الاحتمالي لضمان ثبات المعرفة")) {
      return t("logStrictModeProbabilisticDisabled");
    }

    // 27. Probabilistic source node missing
    if (text.includes("الاستدلال الاحتمالي") && text.includes("غير موجود في الذاكرة الحالية")) {
      const parts = text.match(/'(.*?)'\s*أو\s*'(.*?)'/);
      const concept_a = parts ? parts[1] : "";
      const concept_b = parts ? parts[2] : "";
      return t("logProbabilisticMissingNodes", { concept_a, concept_b });
    }

    // 28. PLN Analysis Trace
    if (text.includes("[PLN]: تم تحليل مسار الترابط الدلالي الاحتمالي")) {
      const parts = text.match(/'(.*?)'\s*و\s*'(.*?)'/);
      const c_a = parts ? parts[1] : "";
      const c_b = parts ? parts[2] : "";
      return t("logPlnPathAnalyzed", { c_a, c_b });
    }
    if (text.includes("مسار القفزات:")) {
      const path = text.split("مسار القفزات:")[1] || "";
      return t("logPlnPathHops", { path });
    }
    if (text.includes("ثقة العلاقات الفردية:")) {
      const steps = text.split("ثقة العلاقات الفردية:")[1] || "";
      return t("logPlnStepsConfidence", { steps });
    }
    if (text.includes("معامل اليقين التراكمي النهائي:")) {
      const confMatch = text.match(/النهائي:\s*([\d.%]+)/);
      const conf = confMatch ? confMatch[1] : "0%";
      return t("logPlnFinalConfidence", { conf });
    }
    if (text.includes("[PLN]: لا يوجد أي مسار ترابط احتمالي")) {
      const parts = text.match(/'(.*?)'\s*و\s*'(.*?)'/);
      const c_a = parts ? parts[1] : "";
      const c_b = parts ? parts[2] : "";
      return t("logPlnNoPath", { c_a, c_b });
    }

    // 29. Rule mining strict limit
    if (text.includes("تم إيقاف حث واستخلاص القواعد المنطقية")) {
      return t("logStrictModeRuleMiningDisabled");
    }

    // 30. Rule mining start
    if (text.includes("حث القواعد الرمزية") && text.includes("جاري فحص الرسوم المعرفية")) {
      return t("logRuleMiningStart");
    }

    // 31. English direct matches
    if (text.includes("Starting Pure DB Reasoning mode...")) {
      return t("logStartingPureDB");
    }
    if (text.includes("Extracting keywords for ontology search...")) {
      return t("logExtractingKeywords");
    }
    if (text.includes("Extracted full connected component for")) {
      const countMatch = text.match(/for\s*(\d+)/);
      const count = countMatch ? countMatch[1] : "0";
      return t("logExtractedConnectedComponent", { count });
    }
    if (text.includes("No matching concepts or facts found in the database.")) {
      return t("logNoFactsFound");
    }
    if (text.includes("Found") && text.includes("relevant knowledge facts.")) {
      const countMatch = text.match(/Found\s*(\d+)/);
      const count = countMatch ? countMatch[1] : "0";
      return t("logFoundFactsCount", { count });
    }
    if (text.includes("Generating fact-based response...")) {
      return t("logGeneratingFactResponse");
    }

    return text;
  };

  const addLog = (text, type = 'info') => {
    const translatedText = translateLogText(text);
    setLogs(prev => [...prev, { type, text: translatedText, time: new Date().toLocaleTimeString(language === 'ar' ? 'ar-EG' : 'en-US') }]);
  };

  // Advanced Cognitive React Handlers
  const fetchMetacognition = async () => {
    setIsMetaLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/metacognition');
      const data = await res.json();
      setMetacognition(data);
    } catch (err) {
      console.error("Failed to fetch metacognition logs:", err);
    } finally {
      setIsMetaLoading(false);
    }
  };

  const runThoughtExperiment = async () => {
    if (!hypothesis.trim()) return;
    setIsThoughtExpLoading(true);
    setThoughtExpLogs([]);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/thought_experiment/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hypothesis, provider, api_key: apiKey, model })
      });
      const data = await res.json();
      setThoughtExpLogs(data.logs || []);
      setThoughtExpEdges(data.hypothetical_edges || []);
      setThoughtExpContradictions(data.contradictions || []);
      fetchGraph();
    } catch (err) {
      console.error("Thought experiment failed:", err);
    } finally {
      setIsThoughtExpLoading(false);
    }
  };

  const runSocraticDialogue = async () => {
    setIsSocraticLoading(true);
    setSocraticLogs([]);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/socratic/dialogue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey, model })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setSocraticDialogue(data.dialogue);
        setSocraticDecision(data.decision);
        setSocraticBelief(data.belief);
        setSocraticLogs(data.logs || []);
        fetchGraph();
      } else {
        await showAlert(data.response || t('socraticError'));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSocraticLoading(false);
    }
  };

  const runPassiveAbsorption = async () => {
    if (!passiveText.trim()) return;
    setIsPassiveLoading(true);
    setPassiveLogs([]);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/absorb/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: passiveText, provider, api_key: apiKey, model, language })
      });
      const data = await res.json();
      setPassiveLogs(data.logs || []);
      setPassiveAbsorbed(data.absorbed_count || 0);
      setPassiveContradictions(data.contradictions_count || 0);
      fetchGraph();
    } catch (err) {
      console.error(err);
    } finally {
      setIsPassiveLoading(false);
    }
  };

  const runWorkspaceDiff = async () => {
    if (!diffWorkspaceName) return;
    setIsDiffLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/workspace/diff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ other_workspace_name: diffWorkspaceName })
      });
      const data = await res.json();
      setWorkspaceDiff(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDiffLoading(false);
    }
  };

  const addProceduralChain = async () => {
    if (!newProcedureName.trim() || !newProcedureSteps.trim()) return;
    setIsProceduralLoading(true);
    const stepsArray = newProcedureSteps.split('\n').map(s => s.trim()).filter(s => s.length > 0);
    try {
      await fetch('http://127.0.0.1:8000/api/procedural/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ procedure_name: newProcedureName, steps: stepsArray, is_global: isProcedureGlobal })
      });
      setNewProcedureName('');
      setNewProcedureSteps('');
      setIsProcedureGlobal(false);
      fetchProcedures();
    } catch (err) {
      console.error(err);
    } finally {
      setIsProceduralLoading(false);
    }
  };

  const fetchProcedures = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/procedural/get');
      const data = await res.json();
      setProcedures(data);
    } catch (err) {
      console.error(err);
    }
  };

  const runFederatedSimulate = async () => {
    if (!federatedQuery.trim()) return;
    setIsFederatedLoading(true);
    setFederatedLogs([]);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/federated/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: federatedQuery })
      });
      const data = await res.json();
      setFederatedPeer(data.peer || '');
      setFederatedConcepts(data.concepts || []);
      setFederatedTriples(data.triples || []);
      setFederatedLogs(data.logs || []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsFederatedLoading(false);
    }
  };

  const runGeneticRuleEvolution = async () => {
    setIsGeneticLoading(true);
    setGeneticLogs([]);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/rules/evolve', {
        method: 'POST'
      });
      const data = await res.json();
      setGeneticLogs(data.logs || []);
      setGeneticCount(data.evolved_count || 0);
      fetchRules();
    } catch (err) {
      console.error(err);
    } finally {
      setIsGeneticLoading(false);
    }
  };



  // Load procedural on mount and initialize logs dynamically
  useEffect(() => {
    setLogs([
      { type: 'info', text: t('initLogMsg'), time: new Date().toLocaleTimeString(language === 'ar' ? 'ar-EG' : 'en-US') }
    ]);
    fetchProcedures();
  }, []);

  // Learn fact logic
  const handleLearn = async () => {
    if (!sentence.trim()) return;
    if (provider !== 'Local' && !apiKey.trim()) {
      addLog(t('apiKeyRequiredLearn'), 'warn');
      await showAlert(t('apiKeyAlert'));
      return;
    }
    setIsWorking(true);
    setContradictions([]);
    setResponse('');
    setParsedData(null);
    setActiveTab('cognitive');
    
    addLog(t('learnAnalyzing', { sentence }), 'process');
    
    try {
      const res = await fetch('http://127.0.0.1:8000/api/learn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sentence, provider, api_key: apiKey, model, language })
      });
      const data = await res.json();
      
      // Append logs returned by Python backend
      if (data.logs) {
        data.logs.forEach(l => {
          if (l.includes('✅') || l.includes('بنجاح')) addLog(l, 'success');
          else if (l.includes('⚠️') || l.includes('تعارض')) addLog(l, 'warn');
          else if (l.includes('⚙️') || l.includes('جاري')) addLog(l, 'process');
          else addLog(l, 'info');
        });
      }

      if (data.status === 'contradiction') {
        setContradictions(data.contradictions);
        addLog(t('contradictionDetectedMsg'), 'warn');
        setActiveTab('cognitive');
      } else if (data.status === 'success') {
        setParsedData(data.parsed);
        setResponse(t('learnSuccessResponse'));
        addLog(t('learnStoreSuccess'), 'success');
        fetchGraph();
        fetchRules();
        fetchCuriosity();
      } else {
        setResponse(data.response || t('unexpectedError'));
      }
    } catch (err) {
      addLog(t('learnConnError'), 'warn');
    } finally {
      setIsWorking(false);
    }
  };

  // Abort saving process logic
  const handleAbort = async () => {
    try {
      addLog(language === 'ar' ? '⚠️ جاري إرسال طلب إلغاء الحفظ...' : '⚠️ Requesting to cancel saving...', 'warn');
      const res = await fetch('http://127.0.0.1:8000/api/status/abort', { method: 'POST' });
      if (res.ok) {
        addLog(language === 'ar' ? '✅ تم إرسال طلب الإيقاف بنجاح.' : '✅ Stop request sent successfully.', 'success');
      }
    } catch (err) {
      console.error("Failed to abort:", err);
    }
  };

  // Query / RAG logic
  const handleQuery = async () => {
    if (!sentence.trim()) return;
    if (provider !== 'Local' && !apiKey.trim()) {
      addLog(t('apiKeyRequiredInference'), 'warn');
      await showAlert(t('apiKeyAlert'));
      return;
    }
    setIsWorking(true);
    setContradictions([]);
    setResponse('');
    setParsedData(null);
    setActiveTab('cognitive');
    
    addLog(t('queryAnalyzing', { sentence }), 'process');
    
    try {
      const res = await fetch('http://127.0.0.1:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sentence, provider, api_key: apiKey, model, language })
      });
      const data = await res.json();
      
      if (data.logs) {
        data.logs.forEach(l => {
          if (l.includes('✅') || l.includes('بنجاح')) addLog(l, 'success');
          else if (l.includes('⚠️')) addLog(l, 'warn');
          else if (l.includes('⚙️')) addLog(l, 'process');
          else addLog(l, 'info');
        });
      }

      if (data.status === 'success') {
        setResponse(data.response);
        setParsedData(data.parsed);
        addLog(t('querySuccessMsg'), 'success');
      } else {
        setResponse(data.response || t('queryEngineFail'));
        addLog(t('queryFailMsg', { detail: data.response || t('queryParseFail') }), 'warn');
      }
    } catch (err) {
      addLog(t('queryConnError'), 'warn');
    } finally {
      setIsWorking(false);
    }
  };

  // Sleep consolidation cycle
  const triggerSleepCycle = async () => {
    setIsSleeping(true);
    setSleepLogs(t('sleepStartingLog') + '\n');
    addLog(t('sleepInitiateMsg'), 'process');
    
    try {
      const res = await fetch('http://127.0.0.1:8000/api/sleep', { method: 'POST' });
      const data = await res.json();
      
      let stepLogs = '';
      if (data.logs) {
        data.logs.forEach(log => {
          stepLogs += `${log}\n`;
        });
      }
      setSleepLogs(stepLogs);
      addLog(t('sleepSuccessMsg'), 'success');
      fetchGraph();
      fetchRules();
      fetchCuriosity();
    } catch (err) {
      setSleepLogs(t('sleepConnError'));
      addLog(t('sleepFailMsg'), 'warn');
    } finally {
      setIsSleeping(false);
    }
  };

  // Run PLN query
  const handlePLN = async (e) => {
    e.preventDefault();
    if (!plnConceptA.trim() || !plnConceptB.trim()) return;
    
    setIsPlnLoading(true);
    setPlnResult('');
    setPlnLogs([]);
    addLog(t('plnCalculatingMsg', { conceptA: plnConceptA, conceptB: plnConceptB }), 'process');
    
    try {
      const res = await fetch('http://127.0.0.1:8000/api/pln', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concept_a: plnConceptA, concept_b: plnConceptB })
      });
      const data = await res.json();
      setPlnResult(data.result);
      setPlnLogs(data.logs || []);
      addLog(t('plnSuccessMsg'), 'success');
    } catch (err) {
      setPlnResult(t('plnError'));
      addLog(t('plnFailMsg'), 'warn');
    } finally {
      setIsPlnLoading(false);
    }
  };

  // Toggle Sandbox Mode
  const handleToggleSandbox = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/sandbox/toggle', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'active') {
        addLog(t('sandboxActivated'), 'warn');
      } else {
        addLog(t('sandboxDeactivated'), 'info');
      }
      fetchGraph();
    } catch (err) {
      addLog(t('sandboxToggleFail'), 'warn');
    }
  };

  // Commit sandbox
  const handleCommitSandbox = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/sandbox/commit', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'committed') {
        addLog(t('sandboxCommitSuccess'), 'success');
      }
      fetchGraph();
      fetchRules();
    } catch (err) {
      addLog(t('sandboxCommitFail'), 'warn');
    }
  };

  // Rollback sandbox
  const handleRollbackSandbox = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/sandbox/rollback', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'rolled_back') {
        addLog(t('sandboxRollbackSuccess'), 'info');
      }
      fetchGraph();
    } catch (err) {
      addLog(t('sandboxRollbackFail'), 'warn');
    }
  };

  // Semantic database pagination & search filters
  const filteredEdges = graphData.edges.filter(edge => {
    const term = (relationsSearch || '').toLowerCase();
    const src = (edge.source || '').toLowerCase();
    const tgt = (edge.target || '').toLowerCase();
    const rel = (edge.relation || '').toLowerCase();
    return src.includes(term) || tgt.includes(term) || rel.includes(term);
  });
  
  const totalPages = Math.ceil(filteredEdges.length / relationsPerPage);
  const paginatedEdges = filteredEdges.slice(
    (relationsPage - 1) * relationsPerPage, 
    relationsPage * relationsPerPage
  );

  return (
    <div className="flex flex-col h-full w-full bg-[#04060d] text-slate-100 overflow-hidden relative" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
      
      {/* 1. Header Ambient Top Bar */}
      <header className="h-16 border-b border-cyan-950/40 bg-slate-950/60 backdrop-blur flex items-center justify-between px-6 z-10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-cyan-400 to-purple-600 flex items-center justify-center pulse-glow">
            <BrainCircuit className="w-5 h-5 text-slate-900" />
          </div>
          <div>
            <h1 className="text-lg font-black tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-sky-300 to-purple-500 font-english">
              LEGEND NEURO-SYMBOLIC
            </h1>
            <p className="text-[10px] text-slate-400 font-medium">{t('subtitle')}</p>
          </div>
        </div>
        
        {/* Workspace select, language select and config */}
        <div className="flex items-center gap-3">
          {/* Workspace mode indicators */}
          {workspaceMode === 'strict' ? (
            <span className="bg-rose-950/40 text-rose-400 border border-rose-900/60 px-3 py-1 rounded-md text-[10px] font-bold flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" />
              {t('workspaceModeStrict')}
            </span>
          ) : (
            <span className="bg-purple-950/40 text-purple-400 border border-purple-900/60 px-3 py-1 rounded-md text-[10px] font-bold flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              {t('workspaceModeActive')}
            </span>
          )}

          {/* Selector dropdown */}
          <div className="flex items-center bg-[#070913] border border-cyan-950 rounded-lg p-1.5">
            <span className="text-[11px] text-slate-400 px-2">{t('workspace')}</span>
            <select 
              value={currentWorkspace} 
              onChange={(e) => selectWorkspace(e.target.value)}
              className="bg-transparent text-cyan-400 text-xs font-bold outline-none border-none cursor-pointer pr-4"
              style={{ direction: 'ltr' }}
            >
              {Object.keys(workspaces).map(ws => (
                <option key={ws} value={ws} className="bg-slate-950 text-slate-200">{ws === 'العقل العام (الافتراضي)' ? t('defaultWorkspaceName') : ws}</option>
              ))}
            </select>
            <button 
              onClick={() => setIsWorkspaceModalOpen(true)}
              className="p-1 text-slate-400 hover:text-cyan-400 transition"
              title={t('newWorkspace')}
            >
              <Plus className="w-4 h-4" />
            </button>
            <button 
              onClick={handleDeleteWorkspace}
              className="p-1 text-slate-500 hover:text-rose-500 transition"
              title={t('deleteWorkspace')}
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button 
              onClick={handleExportWorkspace}
              className="p-1 text-slate-400 hover:text-green-400 transition border-l border-cyan-950/40 pl-1.5 ml-0.5"
              title={t('exportWorkspace')}
            >
              <Download className="w-4 h-4" />
            </button>
            <button 
              onClick={handleImportWorkspace}
              className="p-1 text-slate-400 hover:text-sky-400 transition"
              title={t('importWorkspace')}
            >
              <Upload className="w-4 h-4" />
            </button>
          </div>

          {/* Language switcher */}
          <div className="flex items-center bg-[#070913] border border-cyan-950 rounded-lg p-1.5">
            <span className="text-[11px] text-slate-400 px-2">{t('languageSelectLabel')}</span>
            <select 
              value={language} 
              onChange={(e) => setLanguage(e.target.value)}
              className="bg-transparent text-cyan-400 text-xs font-bold outline-none border-none cursor-pointer"
              style={{ direction: 'ltr' }}
            >
              {supportedLanguages.map(lang => (
                <option key={lang.code} value={lang.code} className="bg-slate-950 text-slate-200">
                  {lang.flag} {lang.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* Main Sandbox alert banner */}
      {inSandbox && (
        <div className="bg-amber-950/80 border-b border-amber-900/60 text-amber-400 text-xs px-6 py-2 flex items-center justify-between font-medium z-10">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 pulse-glow-purple" />
            <span>{t('sandboxWarning')}</span>
          </div>
          <div className="flex gap-2">
            <button onClick={handleCommitSandbox} className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold px-3 py-1 rounded text-[11px] transition">{t('sandboxCommit')}</button>
            <button onClick={handleRollbackSandbox} className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-3 py-1 rounded text-[11px] transition">{t('sandboxRollback')}</button>
          </div>
        </div>
      )}

      {/* 2. Page Content Body */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* RIGHT (Control Side) - Form controls, parameters, live console */}
        <aside className="w-96 border-l border-cyan-950/40 bg-slate-950/30 flex flex-col p-4 gap-4 overflow-y-auto z-10">
          
          {/* LLM & Model Config Panel */}
          <div className="glass-panel glow-cyan-border p-4 flex flex-col gap-3">
            <h2 className="text-xs font-black tracking-wide text-cyan-400 flex items-center gap-2">
              <Layers className="w-4 h-4" />
              {t('engineSettings')}
            </h2>
            
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-slate-400 font-medium">{t('provider')}</label>
              <select 
                value={provider} 
                onChange={(e) => handleProviderChange(e.target.value)}
                className="cyber-input py-1.5 text-xs bg-slate-950 border-cyan-900 animate-pulse-once"
              >
                <option value="Google">Google API {language === 'ar' ? '(الافتراضي)' : '(Default)'}</option>
                <option value="Groq">Groq High-Speed API</option>
                <option value="OpenRouter">OpenRouter Gateway</option>
                <option value="Local">Local Models (Llama.cpp)</option>
              </select>
            </div>

            {provider !== 'Local' && (
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-slate-400 font-medium">{t('apiKey', { provider })}</label>
                <input 
                  type="password"
                  placeholder={t('apiKeyPlaceholder', { provider })}
                  value={apiKeys[provider] || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setApiKeys(prev => ({ ...prev, [provider]: val }));
                  }}
                  className="cyber-input py-1.5 text-xs bg-slate-950 border-cyan-900 text-left font-mono"
                />
                <span className="text-[9px] text-emerald-400/80 mt-0.5">{t('apiKeyNote')}</span>
              </div>
            )}

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-slate-400 font-medium">{t('llmModel')}</label>
              <select 
                value={model} 
                onChange={(e) => setModel(e.target.value)}
                className="cyber-input py-1.5 text-xs bg-slate-950 border-cyan-900"
              >
                {provider === 'OpenRouter' ? (
                  <>
                    <optgroup label={t('freeModels')}>
                      {openRouterModels.free.map(m => (
                        <option key={m.id} value={m.id}>💚 {m.name} [{t('freeLabel')}]</option>
                      ))}
                    </optgroup>
                    <optgroup label={t('paidModels')}>
                      {openRouterModels.paid.map(m => (
                        <option key={m.id} value={m.id}>💎 {m.name}</option>
                      ))}
                    </optgroup>
                  </>
                ) : provider === 'Local' ? (
                  localModels.map(m => (
                    <option key={m} value={m}>💻 {m}</option>
                  ))
                ) : (
                  DEFAULT_KEYS[provider]?.models.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))
                )}
              </select>
            </div>
          </div>

          {/* Interactive Text input & Execution buttons */}
          <div className="glass-panel glow-cyan-border p-4 flex flex-col gap-3">
            <h2 className="text-xs font-black tracking-wide text-cyan-400 flex items-center gap-2">
              <BookOpen className="w-4 h-4" />
              {t('teachOrQuery')}
            </h2>

            {activeNode && (
              <div className="flex items-center justify-between bg-cyan-950/30 border border-cyan-900/60 rounded-xl p-2.5 text-xs text-slate-300 slide-in">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  <span>{t('activeNode', { node: activeNode })}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => {
                      setSentence(activeNode);
                    }}
                    title={t('useNode')}
                    className="px-2 py-1 bg-slate-900 hover:bg-slate-800 rounded border border-slate-800 text-[10px] font-bold transition cursor-pointer text-cyan-400 hover:text-cyan-300"
                  >
                    {t('useNode')}
                  </button>
                  <button
                    onClick={() => handleDeleteNode(activeNode)}
                    title={t('deleteNode')}
                    className="p-1 bg-rose-950/60 hover:bg-rose-900/80 text-rose-400 hover:text-rose-300 border border-rose-900/40 rounded transition active:scale-95 cursor-pointer flex items-center gap-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span className="text-[10px] font-bold">{t('deleteNode')}</span>
                  </button>
                </div>
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <textarea
                placeholder={t('sentencePlaceholder')}
                value={sentence}
                onChange={(e) => setSentence(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (e.ctrlKey || e.metaKey || e.shiftKey) {
                      // Let browser insert newline
                    } else {
                      e.preventDefault();
                      if (!isWorking && sentence.trim()) {
                        handleLearn();
                      }
                    }
                  }
                }}
                className="cyber-input h-24 text-xs resize-none"
              />
            </div>

            <div className="flex gap-2">
              <button 
                onClick={handleLearn} 
                disabled={isWorking || !sentence.trim()} 
                className="cyber-btn flex-1 text-[11px] font-bold"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {t('learnBtn')}
              </button>
              <button 
                onClick={handleQuery} 
                disabled={isWorking || !sentence.trim()} 
                className="cyber-btn-secondary flex-1 text-[11px] font-bold"
              >
                <HelpCircle className="w-3.5 h-3.5" />
                {t('queryBtn')}
              </button>
            </div>
          </div>

          {/* Cyberpunk Live Process Logs terminal */}
          <div className="flex-1 glass-panel glow-purple-border p-4 flex flex-col min-h-[220px] overflow-hidden">
            <h2 className="text-xs font-black tracking-wide text-purple-400 flex items-center justify-between gap-2 mb-2">
              <span className="flex items-center gap-2">
                <Database className="w-4 h-4 animate-pulse" />
                {t('liveLogsTitle')}
              </span>
              <div className="flex items-center gap-1.5">
                <button 
                  onClick={() => {
                    const logsText = logs.map(l => `[${l.time || ''}] [${(l.type || '').toUpperCase()}] ${l.text || ''}`).join('\n');
                    navigator.clipboard.writeText(logsText);
                    addLog(t('toastLogsCopied'), "success");
                  }}
                  title={t('copyLogsBtn')}
                  className="p-1.5 hover:bg-purple-950/60 rounded-md border border-purple-900/40 text-purple-400 hover:text-purple-300 transition flex items-center justify-center active:scale-95 cursor-pointer"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
                <button 
                  onClick={() => {
                    setLogs([{ type: 'info', text: t('clearLogsSuccess'), time: new Date().toLocaleTimeString(language === 'ar' ? 'ar-EG' : 'en-US') }]);
                  }}
                  title={t('clearLogsBtn')}
                  className="p-1.5 hover:bg-rose-950/60 rounded-md border border-rose-900/40 text-rose-400 hover:text-rose-300 transition flex items-center justify-center active:scale-95 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </h2>
            
            <div className="flex-1 bg-slate-950/80 border border-purple-950/60 rounded-lg p-2.5 overflow-y-auto font-mono text-[10px] leading-relaxed flex flex-col gap-1.5">
              {logs.map((log, index) => (
                <div key={index} className="flex flex-col border-b border-slate-900/40 pb-1">
                  <div className="flex justify-between items-center text-[8px] text-slate-500 mb-0.5">
                    <span>{log.time}</span>
                    <span className={`px-1.5 py-0.2 rounded text-[7px] font-bold uppercase tracking-wider ${
                      log.type === 'success' ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/60' :
                      log.type === 'warn' ? 'bg-amber-950/40 text-amber-400 border border-amber-900/60' :
                      log.type === 'process' ? 'bg-cyan-950/40 text-cyan-400 border border-cyan-900/60' :
                      'bg-slate-900 text-slate-400 border border-slate-800'
                    }`}>
                      {log.type}
                    </span>
                  </div>
                  <span className={
                    log.type === 'success' ? 'text-emerald-400 font-bold' :
                    log.type === 'warn' ? 'text-amber-400 font-bold' :
                    log.type === 'process' ? 'text-cyan-400' : 'text-slate-300'
                  }>
                    {log.text}
                  </span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </aside>

        {/* LEFT (Dynamic Graph and Tabs Area) */}
        <main className="flex-1 flex flex-col p-4 overflow-hidden gap-4">
          
          {/* Top Control Bar with Physics Graph Toggle */}
          <div className="flex items-center justify-between bg-slate-950/40 border border-cyan-950/40 rounded-xl p-3 shrink-0">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-xs font-bold text-slate-300">{t('graphToggleTitle')}</span>
            </div>
            
            <div className="flex items-center gap-3">
              <span className="text-[10px] text-slate-400 font-bold">{t('graphToggleLabel')}</span>
              <label className="relative inline-flex items-center cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={showPhysicsGraph} 
                  onChange={() => setShowPhysicsGraph(!showPhysicsGraph)} 
                  className="sr-only peer" 
                />
                <div className="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-4 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-500"></div>
              </label>
            </div>
          </div>

          {/* Top Panel - Glorious Active Physics Neural Net Graph */}
          {showPhysicsGraph && (
            <>
              <section 
                style={{ height: `${graphHeight}px` }}
                className="min-h-[200px] glass-panel glow-cyan-border p-3 flex flex-col overflow-hidden relative shrink-0"
              >
                <div className="absolute top-4 right-4 z-10 flex items-center gap-2 pointer-events-none">
                  <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                  <span className="text-[10px] text-slate-400 font-bold bg-slate-950/80 px-2 py-0.5 rounded border border-cyan-950">{t('graphInteractiveLabel')}</span>
                </div>
                
                <div className="flex-1 rounded-xl overflow-hidden bg-slate-950/20">
                  <PhysicsGraph 
                    nodes={graphData.nodes} 
                    edges={graphData.edges} 
                    activeNode={activeNode}
                    lang={language}
                    onNodeClick={(nodeId) => {
                      setActiveNode(nodeId);
                      setSentence(nodeId);
                      addLog(t('nodeSelectedMsg', { nodeId }), 'info');
                    }}
                  />
                </div>
              </section>

              {/* Draggable Divider Line */}
              <div 
                onMouseDown={startDrag}
                className="h-2 w-full cursor-row-resize flex items-center justify-center hover:bg-cyan-900/30 active:bg-cyan-800/40 rounded transition-all group z-20"
                title={t('graphDraggable')}
              >
                <div className="w-24 h-1 rounded-full bg-cyan-950 border border-cyan-900/60 group-hover:bg-cyan-400 group-active:bg-cyan-300 transition" />
              </div>
            </>
          )}

          {/* Bottom Panel - Tabs Navigation & Content */}
          <section className="flex-1 glass-panel glow-purple-border p-4 flex flex-col overflow-hidden">
            
            {/* Tabs List */}
            <div className="flex border-b border-purple-950/40 pb-2 mb-3 gap-2 overflow-x-auto">
              <button 
                onClick={() => setActiveTab('cognitive')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                  activeTab === 'cognitive' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BrainCircuit className="w-3.5 h-3.5" />
                {t('tabCognitive')}
              </button>
              
              <button 
                onClick={() => setActiveTab('database')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                  activeTab === 'database' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                {t('tabDatabase', { count: graphData.edges.length })}
              </button>

              <button 
                onClick={() => setActiveTab('sleep')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                  activeTab === 'sleep' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Moon className="w-3.5 h-3.5" />
                {t('tabSleep')}
              </button>

              <button 
                onClick={() => setActiveTab('rules')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                  activeTab === 'rules' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                {t('tabRules')}
              </button>

              <button 
                onClick={() => setActiveTab('sandbox')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                  activeTab === 'sandbox' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Shield className="w-3.5 h-3.5" />
                {t('tabSandbox')}
              </button>

              <button 
                onClick={() => {
                  setActiveTab('stats');
                  fetchStats();
                }}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
                  activeTab === 'stats' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BarChart2 className="w-3.5 h-3.5" />
                {t('tabStats')}
              </button>

              <button 
                onClick={() => {
                  setActiveTab('advanced');
                  fetchMetacognition();
                }}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
                  activeTab === 'advanced' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
                {t('tabAdvanced')}
              </button>

              <button 
                onClick={() => setActiveTab('documentation')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
                  activeTab === 'documentation' ? 'bg-purple-950/80 text-purple-400 border border-purple-800' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
                {t('tabDocumentation')}
              </button>
            </div>

            {/* Tab Contents */}
            <div className="flex-1 overflow-y-auto">
              
              {/* Tab 1: Cognitive Response */}
              {activeTab === 'cognitive' && (
                <div className="slide-in flex flex-col gap-4 h-full">
                  {contradictions.length > 0 && (
                    <div className="border border-rose-950 bg-rose-950/20 text-rose-400 p-4 rounded-xl flex flex-col gap-2">
                      <div className="flex items-center gap-2 text-sm font-bold">
                        <AlertTriangle className="w-5 h-5 text-rose-500 animate-bounce" />
                        <span>{t('contradictionWarning')}</span>
                      </div>
                      <p className="text-xs">{t('contradictionSub')}</p>
                      <div className="flex flex-col gap-1.5 mt-1">
                        {contradictions.map((c, i) => (
                          <div key={i} className="bg-rose-950/60 p-2.5 rounded border border-rose-900/40 text-[11px] leading-relaxed">
                            {c}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {response && (
                    <div className="border border-cyan-950/50 bg-cyan-950/10 p-4 rounded-xl flex flex-col gap-2">
                      <h3 className="text-xs font-bold text-cyan-400 flex items-center justify-between gap-1.5">
                        <span className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4" />
                          {t('answerTitle')}
                        </span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(response);
                            addLog(t('toastAnswerCopied'), "success");
                          }}
                          title={t('copyAnswerBtn')}
                          className="px-2 py-1 rounded bg-cyan-950/50 hover:bg-cyan-900 border border-cyan-900/40 text-cyan-400 hover:text-cyan-300 text-[10px] font-bold transition flex items-center gap-1 active:scale-95 cursor-pointer"
                        >
                          <Copy className="w-3.5 h-3.5" />
                          {t('copyAnswerBtn')}
                        </button>
                      </h3>
                      <p className="text-sm leading-relaxed text-slate-100">{response}</p>
                    </div>
                  )}

                  {parsedData && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Classifications & Properties block */}
                      <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-3.5">
                        <h4 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1">
                          <Layers className="w-3.5 h-3.5 text-purple-400" />
                          {t('taxonomiesTitle')}
                        </h4>
                        <div className="flex flex-wrap gap-1.5">
                          {parsedData.entities && Array.isArray(parsedData.entities) && parsedData.entities.filter(Boolean).map((sub, i) => (
                            <span key={i} className="bg-purple-950/40 text-purple-300 border border-purple-900/60 text-[10px] px-2 py-0.5 rounded-full font-bold">
                              {t('taxonomyIsType', { 
                                sub: typeof sub?.name === 'object' ? JSON.stringify(sub.name) : String(sub?.name || 'Unknown'), 
                                parent: typeof (sub?.abstract_type || sub?.type) === 'object' ? JSON.stringify(sub.abstract_type || sub.type) : String(sub?.abstract_type || sub?.type || 'Entity') 
                              })}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-3.5">
                        <h4 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1">
                          <Database className="w-3.5 h-3.5 text-cyan-400" />
                          {t('triplesTitle')}
                        </h4>
                        <div className="flex flex-col gap-1.5">
                          {parsedData.relations && Array.isArray(parsedData.relations) && parsedData.relations.filter(Boolean).map((rel, i) => (
                            <div key={i} className="text-[11px] text-slate-300 flex items-center gap-2 bg-slate-900/60 p-2 rounded">
                              <span className="text-cyan-400 font-bold">{typeof rel?.subject === 'object' ? JSON.stringify(rel.subject) : String(rel?.subject || '')}</span>
                              <span className="text-slate-500">← ({typeof rel?.relation === 'object' ? JSON.stringify(rel.relation) : String(rel?.relation || '')}) ←</span>
                              <span className="text-cyan-400 font-bold">{typeof rel?.object === 'object' ? JSON.stringify(rel.object) : String(rel?.object || '')}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {!response && !parsedData && contradictions.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-16 text-slate-500 gap-2">
                      <BrainCircuit className="w-12 h-12 stroke-[1] text-slate-600 animate-pulse" />
                      <span className="text-xs">{t('emptyResponse')}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 2: Semantic Relations Database Table */}
              {activeTab === 'database' && (
                <div className="slide-in flex flex-col gap-3 h-full">
                  <div className="flex justify-between items-center gap-3">
                    <input 
                      type="text" 
                      placeholder={t('searchPlaceholder')}
                      value={relationsSearch}
                      onChange={(e) => { setRelationsSearch(e.target.value); setRelationsPage(1); }}
                      className="cyber-input flex-1 py-1 text-xs"
                    />
                    <button onClick={fetchGraph} className="cyber-btn-secondary py-1 text-xs flex items-center gap-1 font-bold">
                      <RefreshCw className="w-3.5 h-3.5" />
                      {t('refreshDb')}
                    </button>
                  </div>

                  {/* Relations table */}
                  <div className="flex-1 bg-slate-950/40 border border-slate-900 rounded-xl overflow-hidden">
                    <table className="w-full border-collapse text-right text-xs">
                      <thead>
                        <tr className="bg-slate-950/80 text-slate-400 border-b border-cyan-950/40 text-[10px] font-bold">
                          <th className="p-3">{t('tableSubject')}</th>
                          <th className="p-3">{t('tableRelation')}</th>
                          <th className="p-3">{t('tableObject')}</th>
                          <th className="p-3 w-32">{t('tableConfidence')}</th>
                          <th className="p-3 w-20 text-center">{t('tableActions')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedEdges.length > 0 ? (
                          paginatedEdges.map((edge, index) => (
                            <tr key={index} className="border-b border-slate-900/30 hover:bg-cyan-950/10 transition">
                              <td className="p-3 font-bold text-cyan-400">{edge.source}</td>
                              <td className="p-3 text-slate-300 font-medium">{edge.relation}</td>
                              <td className="p-3 font-bold text-cyan-400">{edge.target}</td>
                              <td className="p-3">
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                    <div 
                                      className="h-full bg-gradient-to-r from-cyan-500 to-purple-500 rounded-full" 
                                      style={{ width: `${edge.confidence * 100}%` }}
                                    />
                                  </div>
                                  <span className="font-mono text-[10px] text-slate-400">{(edge.confidence).toFixed(2)}</span>
                                </div>
                              </td>
                              <td className="p-3 text-center">
                                <button 
                                  onClick={() => handleDeleteRelation(edge.source, edge.relation, edge.target)}
                                  title={t('deleteRuleTitle')}
                                  className="p-1 text-rose-500 hover:text-rose-400 hover:bg-rose-950/40 border border-transparent hover:border-rose-900/40 rounded transition active:scale-95 cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="5" className="text-center p-8 text-slate-500">{t('emptyRelations')}</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination control */}
                  {totalPages > 1 && (
                    <div className="flex justify-center items-center gap-2 mt-2">
                      <button 
                        onClick={() => setRelationsPage(p => Math.max(1, p - 1))}
                        disabled={relationsPage === 1}
                        className="cyber-btn-secondary py-0.5 px-2.5 text-[10px] font-bold"
                      >
                        {t('prevBtn')}
                      </button>
                      <span className="text-[10px] text-slate-400">{t('pageOf', { page: relationsPage, total: totalPages })}</span>
                      <button 
                        onClick={() => setRelationsPage(p => Math.min(totalPages, p + 1))}
                        disabled={relationsPage === totalPages}
                        className="cyber-btn-secondary py-0.5 px-2.5 text-[10px] font-bold"
                      >
                        {t('nextBtn')}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 3: Sleep & Curiosity */}
              {activeTab === 'sleep' && (
                <div className="slide-in grid grid-cols-1 lg:grid-cols-2 gap-4 h-full">
                  
                  {/* Left Side: Sleep Consolidation */}
                  <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-4 flex flex-col gap-3 min-h-[300px]">
                    <div className="flex justify-between items-center">
                      <h3 className="text-xs font-bold text-purple-400 flex items-center gap-1.5">
                        <Moon className="w-4 h-4" />
                        {t('sleepTitle')}
                      </h3>
                      {workspaceMode === 'strict' && (
                        <span className="bg-rose-950/60 text-rose-400 text-[8px] px-2 py-0.5 rounded border border-rose-900">{t('strictLabel')}</span>
                      )}
                    </div>
                    
                    <p className="text-[11px] leading-relaxed text-slate-400">
                      {t('sleepDesc')}
                    </p>

                    <button
                      onClick={triggerSleepCycle}
                      disabled={isSleeping || workspaceMode === 'strict'}
                      className="cyber-btn cyber-btn-purple text-xs font-bold w-full"
                    >
                      {isSleeping ? t('sleepActiveBtn') : t('sleepTriggerBtn')}
                    </button>

                    <div className="flex-1 bg-slate-950 border border-purple-950 rounded-lg p-3 font-mono text-[10px] text-purple-300 leading-relaxed overflow-y-auto min-h-[140px] whitespace-pre-wrap">
                      {sleepLogs || t('sleepPlaceholder')}
                    </div>
                  </div>

                  {/* Right Side: Active Curiosity Grid */}
                  <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-4 flex flex-col gap-3 min-h-[300px]">
                    <div className="flex justify-between items-center">
                      <h3 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4" />
                        {t('curiosityTitle')}
                      </h3>
                      <button 
                        onClick={fetchCuriosity} 
                        disabled={isCuriosityLoading || workspaceMode === 'strict'}
                        className="p-1 text-slate-400 hover:text-cyan-400 transition"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <p className="text-[11px] leading-relaxed text-slate-400">
                      {t('curiosityDesc')}
                    </p>

                    <div className="flex-1 overflow-y-auto flex flex-col gap-2.5 pr-1">
                      {workspaceMode === 'strict' ? (
                        <div className="flex-1 flex items-center justify-center text-center text-slate-500 text-xs p-6">
                          {t('curiosityStrict')}
                        </div>
                      ) : curiosityQuestions.length > 0 ? (
                        curiosityQuestions.map((q, i) => (
                          <div 
                            key={i} 
                            className="bg-slate-900/60 border border-cyan-950/40 hover:border-cyan-500/50 p-3 rounded-lg flex flex-col gap-2 transition hover:bg-cyan-950/5 cursor-pointer"
                            onClick={() => {
                              setSentence(q.text_to_paste);
                              addLog(t('curiosityCopied', { template: q.text_to_paste }), 'info');
                            }}
                          >
                            <span className="text-[11px] text-slate-200 font-bold leading-normal">{q.question}</span>
                            <div className="flex justify-between items-center mt-1">
                              <span className="text-[8px] text-slate-500">{t('curiosityTemplateNote')}</span>
                              <span className="bg-cyan-950 text-cyan-400 text-[9px] px-2 py-0.5 rounded font-bold">{t('curiosityAction')}</span>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="flex-1 flex items-center justify-center text-center text-slate-600 text-xs p-6">
                          {isCuriosityLoading ? t('curiosityChecking') : t('curiosityEmpty')}
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              )}

              {/* Tab 4: Rules & PLN */}
              {activeTab === 'rules' && (
                <div className="slide-in grid grid-cols-1 lg:grid-cols-2 gap-4 h-full">
                  
                  {/* Left Side: Rules list */}
                  <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-4 flex flex-col gap-3 min-h-[300px]">
                    <div className="flex justify-between items-center flex-wrap gap-2">
                      <h3 className="text-xs font-bold text-purple-400 flex items-center gap-1.5">
                        <Layers className="w-4 h-4" />
                        {t('ruleListTitle')}
                      </h3>
                      <div className="flex gap-2">
                        <button 
                          onClick={() => setShowAddRuleForm(!showAddRuleForm)}
                          type="button"
                          className="cyber-btn-secondary py-0.5 px-2 text-[10px] font-bold border-purple-800 text-purple-400"
                        >
                          {showAddRuleForm ? t('cancelBtn') : t('addRuleBtn')}
                        </button>
                        <button 
                          onClick={async () => {
                            addLog(t('inductRulesRunning'), 'process');
                            const res = await fetch('http://127.0.0.1:8000/api/rules/induct', { method: 'POST' });
                            const data = await res.json();
                            data.logs.forEach(l => addLog(l, 'info'));
                            fetchRules();
                          }}
                          disabled={workspaceMode === 'strict'}
                          className="cyber-btn-secondary py-0.5 px-2 text-[10px] font-bold"
                        >
                          {t('inductRulesBtn')}
                        </button>
                      </div>
                    </div>

                    {showAddRuleForm && (
                      <form onSubmit={handleAddRule} className="bg-purple-950/20 border border-purple-900/50 p-3 rounded-xl flex flex-col gap-2.5 animate-slide-down">
                        <div className="text-[10px] text-purple-400 font-bold border-b border-purple-950 pb-1 flex justify-between items-center">
                          <span>{t('customRuleTitle')}</span>
                          <span className="text-slate-500 font-normal">{t('customRuleSubtitle')}</span>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-2">
                          <div className="flex flex-col gap-1">
                            <label className="text-[9px] text-slate-400">{t('ruleNameLabel')}:</label>
                            <input 
                              type="text" 
                              placeholder={t('rulePlaceholderName')}
                              value={newRuleName}
                              onChange={(e) => setNewRuleName(e.target.value)}
                              className="cyber-input py-1 text-xs"
                              required
                            />
                          </div>
                          <div className="flex flex-col gap-1">
                            <label className="text-[9px] text-slate-400">{t('ruleConfidenceLabel')}</label>
                            <input 
                              type="number" 
                              step="0.05"
                              min="0.1"
                              max="1.0"
                              value={newRuleConfidence}
                              onChange={(e) => setNewRuleConfidence(e.target.value)}
                              className="cyber-input py-1 text-xs"
                              required
                            />
                          </div>
                        </div>

                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] text-slate-400">{t('ruleAntecedentsLabel')}</label>
                          <textarea 
                            rows="2"
                            placeholder={t('rulePlaceholderAntecedents')}
                            value={newRuleAntecedents}
                            onChange={(e) => setNewRuleAntecedents(e.target.value)}
                            className="cyber-input py-1 text-xs leading-normal font-mono"
                            required
                          />
                        </div>

                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] text-slate-400">{t('ruleConsequentLabel')}</label>
                          <input 
                            type="text" 
                            placeholder={t('rulePlaceholderConsequent')}
                            value={newRuleConsequent}
                            onChange={(e) => setNewRuleConsequent(e.target.value)}
                            className="cyber-input py-1 text-xs font-mono"
                            required
                          />
                        </div>

                        <button 
                          type="submit"
                          className="cyber-btn cyber-btn-purple py-1 text-xs font-bold"
                        >
                          {t('saveRuleBtn')}
                        </button>
                      </form>
                    )}

                    <div className="flex-1 overflow-y-auto flex flex-col gap-2">
                      {rules.length > 0 ? (
                        rules.map((rule, i) => (
                          <div key={i} className="bg-slate-900/60 p-3 rounded-lg border border-purple-950/40 flex justify-between items-start gap-2 text-[11px] leading-relaxed hover:border-purple-800 transition">
                            <div className="flex-1 flex flex-col gap-1.5">
                              <div className="flex items-center flex-wrap gap-1.5 text-purple-300 font-bold text-right" style={{ direction: 'rtl' }}>
                                {rule.rule_name && (
                                  <span className="text-[9px] bg-purple-950/80 text-purple-400 border border-purple-800 px-1.5 py-0.5 rounded font-mono select-all">{rule.rule_name}</span>
                                )}
                                <span>{t('ruleIf')}</span>
                                <span className="text-cyan-400">({rule.antecedent.relation})</span>
                                <span>{t('ruleThen')}</span>
                                <span className="text-emerald-400">({rule.consequent.relation})</span>
                              </div>
                              <div className="flex gap-4 text-[9px] text-slate-500">
                                <span>{t('ruleSupport')}: {rule.support}</span>
                                <span>{t('ruleConfidence')}: {(rule.confidence * 100).toFixed(1)}%</span>
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleDeleteRule(rule.rule_name)}
                              className="p-1 text-rose-500 hover:text-rose-400 hover:bg-rose-950/40 border border-transparent hover:border-rose-900/40 rounded transition active:scale-95 cursor-pointer"
                              title={t('deleteRuleTitle')}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))
                      ) : (
                        <div className="flex-1 flex items-center justify-center text-slate-500 text-xs">{t('noRules')}</div>
                      )}
                    </div>
                  </div>

                  {/* Right Side: PLN paths */}
                  <form onSubmit={handlePLN} className="bg-slate-950/40 border border-slate-900 rounded-xl p-4 flex flex-col gap-3 min-h-[300px]">
                    <h3 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                      <BrainCircuit className="w-4 h-4" />
                      {t('plnTitle')}
                    </h3>

                    <div className="grid grid-cols-2 gap-2.5">
                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] text-slate-400 font-medium">{t('plnConceptALabel')}</label>
                        <input 
                          type="text" 
                          placeholder={t('plnPlaceholderA')} 
                          value={plnConceptA}
                          onChange={(e) => setPlnConceptA(e.target.value)}
                          className="cyber-input py-1 text-xs"
                        />
                      </div>
                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] text-slate-400 font-medium">{t('plnConceptBLabel')}</label>
                        <input 
                          type="text" 
                          placeholder={t('plnPlaceholderB')} 
                          value={plnConceptB}
                          onChange={(e) => setPlnConceptB(e.target.value)}
                          className="cyber-input py-1 text-xs"
                        />
                      </div>
                    </div>

                    <button 
                      type="submit" 
                      disabled={isPlnLoading || !plnConceptA.trim() || !plnConceptB.trim()}
                      className="cyber-btn text-xs font-bold w-full"
                    >
                      {isPlnLoading ? t('plnCalculating') : t('plnCalculateBtn')}
                    </button>

                    <div className="flex-1 bg-slate-950 border border-cyan-950 rounded-lg p-3 overflow-y-auto flex flex-col gap-2 min-h-[120px]">
                      {plnResult && (
                        <div className="border-b border-slate-900/60 pb-2 mb-2 text-xs leading-relaxed text-slate-200 font-bold">
                          💡 {t('plnResultTitle')} {plnResult}
                        </div>
                      )}
                      
                      <div className="flex flex-col gap-1.5 text-[10px] font-mono text-cyan-300">
                        {plnLogs.map((log, i) => (
                          <div key={i} className="leading-relaxed border-b border-slate-900/20 pb-1">
                            {log}
                          </div>
                        ))}
                        {!plnResult && plnLogs.length === 0 && (
                          <div className="text-slate-500 text-xs text-center py-8">{t('plnEmptyLogs')}</div>
                        )}
                      </div>
                    </div>
                  </form>

                </div>
              )}

              {/* Tab 5: Counterfactual Sandbox */}
              {activeTab === 'sandbox' && (
                <div className="slide-in flex flex-col gap-4 h-full p-2 max-w-2xl">
                  <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-4 flex flex-col gap-3">
                    <h3 className="text-sm font-bold text-amber-400 flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5" />
                      {t('sandboxTitle')}
                    </h3>
                    
                    <p className="text-xs leading-relaxed text-slate-300">
                      {t('sandboxDesc')}
                    </p>

                    <div className="flex flex-col gap-2.5 mt-3">
                      <div className="flex justify-between items-center bg-slate-950/80 p-3 rounded-lg border border-slate-900">
                        <span className="text-xs font-bold text-slate-200">{t('sandboxStatusLabel')}</span>
                        {inSandbox ? (
                          <span className="bg-amber-950/80 text-amber-400 border border-amber-900/60 text-[10px] font-black px-2.5 py-1 rounded animate-pulse">{t('sandboxActive')}</span>
                        ) : (
                          <span className="bg-slate-900 text-slate-500 text-[10px] font-bold px-2.5 py-1 rounded">{t('sandboxInactive')}</span>
                        )}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2">
                        <button
                          onClick={handleToggleSandbox}
                          className={`cyber-btn font-bold text-xs ${inSandbox ? 'cyber-btn-purple' : ''}`}
                        >
                          {inSandbox ? t('sandboxToggleClose') : t('sandboxToggleOpen')}
                        </button>
                        
                        <button
                          onClick={handleCommitSandbox}
                          disabled={!inSandbox}
                          className="cyber-btn cyber-btn-emerald font-bold text-xs"
                        >
                          {t('sandboxCommit')}
                        </button>
                        
                        <button
                          onClick={handleRollbackSandbox}
                          disabled={!inSandbox}
                          className="cyber-btn-secondary text-rose-400 border-rose-900 hover:bg-rose-950/30 font-bold text-xs"
                        >
                          {t('sandboxRollback')}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 6: Knowledge Statistics & Brain Reset */}
              {activeTab === 'stats' && (
                <div className="slide-in flex flex-col gap-4 h-full p-2 overflow-y-auto">
                  {isStatsLoading && !stats ? (
                    <div className="flex flex-col items-center justify-center py-12 gap-3">
                      <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin" />
                      <span className="text-xs text-slate-400 font-bold">{t('statsLoading')}</span>
                    </div>
                  ) : stats ? (
                    <div className="flex flex-col gap-5">
                      
                      {/* Top Metrics Cards Grid */}
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        <div className="glass-panel p-3 border-cyan-900/60 bg-cyan-950/10 flex flex-col items-center justify-center text-center">
                          <span className="text-[10px] text-slate-400 font-bold mb-1">{t('statsTotalConcepts')}</span>
                          <span className="text-xl font-black text-cyan-400 tracking-tight">{stats.total_concepts}</span>
                        </div>
                        <div className="glass-panel p-3 border-purple-900/60 bg-purple-950/10 flex flex-col items-center justify-center text-center">
                          <span className="text-[10px] text-slate-400 font-bold mb-1">{t('statsTotalTriples')}</span>
                          <span className="text-xl font-black text-purple-400 tracking-tight">{stats.total_triples}</span>
                        </div>
                        <div className="glass-panel p-3 border-emerald-900/60 bg-emerald-950/10 flex flex-col items-center justify-center text-center">
                          <span className="text-[10px] text-slate-400 font-bold mb-1">{t('statsTotalInstances')}</span>
                          <span className="text-xl font-black text-emerald-400 tracking-tight">{stats.total_instances}</span>
                        </div>
                        <div className="glass-panel p-3 border-amber-900/60 bg-amber-950/10 flex flex-col items-center justify-center text-center">
                          <span className="text-[10px] text-slate-400 font-bold mb-1">{t('statsMaxDepth')}</span>
                          <span className="text-xl font-black text-amber-400 tracking-tight">{stats.max_depth}</span>
                        </div>
                        <div className="glass-panel p-3 border-rose-900/60 bg-rose-950/10 flex flex-col items-center justify-center text-center">
                          <span className="text-[10px] text-slate-400 font-bold mb-1">{t('statsDbSize')}</span>
                          <span className="text-xs font-black text-rose-400 tracking-tight mt-1">{stats.db_size_kb} KB</span>
                        </div>
                      </div>

                      {/* Detailed Analyses Blocks */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        
                        {/* Top Connected Concepts card list */}
                        <div className="glass-panel border-cyan-950/60 p-4 flex flex-col gap-2">
                          <h4 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5 border-b border-cyan-950/40 pb-2 mb-1">
                            <Network className="w-3.5 h-3.5" />
                            {t('statsTopEntities')}
                          </h4>
                          {stats.top_connected && stats.top_connected.length > 0 ? (
                            <div className="flex flex-col gap-2 mt-1">
                              {stats.top_connected.map(([concept, degree], idx) => (
                                <div key={idx} className="flex justify-between items-center bg-slate-950/60 px-3 py-2 rounded border border-slate-900/40 text-xs">
                                  <span className="font-bold text-slate-200">{concept}</span>
                                  <span className="text-[10px] text-cyan-400 font-bold bg-cyan-950/40 border border-cyan-900/40 px-2 py-0.5 rounded">{degree} {t('statsLinksCount')}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-xs text-slate-500 text-center py-6">{t('statsEmptyDb')}</div>
                          )}
                        </div>

                        {/* Top Predicates card list */}
                        <div className="glass-panel border-purple-950/60 p-4 flex flex-col gap-2">
                          <h4 className="text-xs font-bold text-purple-400 flex items-center gap-1.5 border-b border-purple-950/40 pb-2 mb-1">
                            <Database className="w-3.5 h-3.5" />
                            {t('statsTopPredicates')}
                          </h4>
                          {stats.top_predicates && stats.top_predicates.length > 0 ? (
                            <div className="flex flex-col gap-2 mt-1">
                              {stats.top_predicates.map(([relation, count], idx) => (
                                <div key={idx} className="flex justify-between items-center bg-slate-950/60 px-3 py-2 rounded border border-slate-900/40 text-xs">
                                  <span className="font-bold text-slate-200">"{relation}"</span>
                                  <span className="text-[10px] text-purple-400 font-bold bg-purple-950/40 border border-purple-900/40 px-2 py-0.5 rounded">{count} {t('statsRepeatsCount')}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-xs text-slate-500 text-center py-6">{t('statsEmptyRelations')}</div>
                          )}
                        </div>

                      </div>

                      {/* Reset Brain / Danger Zone */}
                      <div className="glass-panel border-rose-950/60 bg-rose-950/5 p-4 rounded-xl flex flex-col gap-3 mt-2 max-w-xl">
                        <h4 className="text-xs font-black text-rose-500 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-rose-500 animate-pulse" />
                          {t('dangerZoneTitle')}
                        </h4>
                        <p className="text-[10px] leading-relaxed text-slate-400">
                          {t('dangerZoneDesc')}
                        </p>
                        <div>
                          <button
                            onClick={handleClearDatabase}
                            className="bg-rose-950/80 hover:bg-rose-900/80 text-rose-200 border border-rose-800 hover:border-rose-700 px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 active:scale-95 cursor-pointer"
                          >
                            <Trash2 className="w-4 h-4" />
                            {t('dangerZoneResetBtn')}
                          </button>
                        </div>
                      </div>

                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 text-center py-12">{t('statsWaiting')}</div>
                  )}
                </div>
              )}

              {/* Tab 7: Advanced Cognitive Suite */}
              {activeTab === 'advanced' && (
                <div className="slide-in flex flex-col gap-4 h-full p-2">
                  <div className="flex gap-2 border-b border-purple-950/40 pb-2 overflow-x-auto">
                    {[
                      { id: 'metacognition', label: t('advSubtabMetacognition'), icon: '🧠' },
                      { id: 'thought', label: t('advSubtabThoughtExperiments'), icon: '🔬' },
                      { id: 'socratic', label: t('advSubtabSocraticDialogue'), icon: '💬' },
                      { id: 'genetic', label: t('advSubtabGeneticRules'), icon: '🧬' },
                      { id: 'passive', label: t('advSubtabBatchAbsorption'), icon: '📥' },
                      { id: 'diff', label: t('advSubtabConceptDiff'), icon: '🔄' },
                      { id: 'procedural', label: t('advSubtabProceduralCognition'), icon: '⛓️' },
                      { id: 'federated', label: t('advSubtabFederatedP2P'), icon: '📡' },
                    ].map(tab => (
                      <button
                        key={tab.id}
                        onClick={() => {
                          localStorage.setItem('legend_advanced_subtab', tab.id);
                          // Force state change by switching state internally
                          setHypothesis(hypothesis => hypothesis + ' ');
                          setTimeout(() => setHypothesis(hypothesis => hypothesis.trim()), 20);
                          if (tab.id === 'metacognition') fetchMetacognition();
                        }}
                        className={`px-3 py-1 rounded-lg text-[10px] font-bold transition whitespace-nowrap cursor-pointer ${
                          (localStorage.getItem('legend_advanced_subtab') || 'metacognition') === tab.id
                            ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                            : 'bg-slate-950 text-slate-400 border border-slate-900 hover:text-slate-200'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  <div className="flex-1 overflow-y-auto">
                    {/* Sub-tab 1: Metacognition */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'metacognition' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="flex justify-between items-center bg-slate-950/60 p-3 rounded-xl border border-slate-900/60">
                          <div>
                            <h3 className="text-xs font-bold text-slate-200">{t('metaEngineTitle')}</h3>
                            <p className="text-[10px] text-slate-400">{t('metaEngineDesc')}</p>
                          </div>
                          <button
                            onClick={fetchMetacognition}
                            disabled={isMetaLoading}
                            className="bg-cyan-950 hover:bg-cyan-900 text-cyan-400 border border-cyan-800 px-3 py-1.5 rounded-lg text-[10px] font-bold transition flex items-center gap-1 cursor-pointer"
                          >
                            <RefreshCw className={`w-3 h-3 ${isMetaLoading ? 'animate-spin' : ''}`} />
                            {t('metaRefreshBtn')}
                          </button>
                        </div>

                        {metacognition ? (
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {/* Health Index Ring */}
                            <div className="glass-panel p-4 flex flex-col items-center justify-center text-center gap-2 border-cyan-950/60">
                              <span className="text-[10px] text-slate-400 font-bold">{t('metaHealthIndex')}</span>
                              <div className="relative w-24 h-24 flex items-center justify-center">
                                <svg className="w-full h-full transform -rotate-90">
                                  <circle cx="48" cy="48" r="40" stroke="rgba(30, 41, 59, 0.4)" strokeWidth="8" fill="transparent" />
                                  <circle cx="48" cy="48" r="40" stroke={metacognition.healthy ? '#10b981' : '#f59e0b'} strokeWidth="8" fill="transparent"
                                    strokeDasharray="251.2" strokeDashoffset={251.2 - (251.2 * metacognition.cognitive_index)} />
                                </svg>
                                <span className="absolute text-xl font-black text-slate-200">%{Math.round(metacognition.cognitive_index * 100)}</span>
                              </div>
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${metacognition.healthy ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-900' : 'bg-amber-950/80 text-amber-400 border border-amber-900'}`}>
                                {metacognition.healthy ? t('metaHealthyMsg') : t('metaUnhealthyMsg')}
                              </span>
                            </div>

                            {/* Cyclic Dependencies */}
                            <div className="glass-panel p-4 flex flex-col gap-2 border-rose-950/60">
                              <span className="text-[10px] text-rose-400 font-bold border-b border-rose-950 pb-1 flex items-center gap-1">{t('metaInfiniteLoopsTitle')}</span>
                              {metacognition.cyclic_dependencies && metacognition.cyclic_dependencies.length > 0 ? (
                                <div className="flex flex-col gap-1.5 overflow-y-auto max-h-32">
                                  {metacognition.cyclic_dependencies.map((cycle, i) => (
                                    <div key={i} className="bg-rose-950/40 border border-rose-900/40 p-1.5 rounded text-[10px] text-rose-300 leading-tight">
                                      {cycle.join(' ➔ ')}
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="text-[10px] text-slate-500 text-center py-6">{t('metaNoLoops')}</div>
                              )}
                            </div>

                            {/* Isolated Components */}
                            <div className="glass-panel p-4 flex flex-col gap-2 border-amber-950/60">
                              <span className="text-[10px] text-amber-400 font-bold border-b border-amber-950 pb-1 flex items-center gap-1">{t('metaIsolatedTitle')}</span>
                              {metacognition.isolated_components && metacognition.isolated_components.length > 0 ? (
                                <div className="flex flex-col gap-1.5 overflow-y-auto max-h-32">
                                  {metacognition.isolated_components.map((comp, i) => (
                                    <div key={i} className="bg-amber-950/40 border border-amber-900/40 p-1.5 rounded text-[10px] text-amber-300 leading-tight">
                                      {comp.join(' - ')}
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="text-[10px] text-slate-500 text-center py-6">{t('metaNoIsolated')}</div>
                              )}
                            </div>

                            {/* Vague Entities */}
                            <div className="glass-panel p-4 md:col-span-3 flex flex-col gap-2 border-slate-900/60">
                              <span className="text-[10px] text-slate-300 font-bold border-b border-slate-950 pb-1">{t('metaVagueConceptsTitle')}</span>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                {metacognition.vague_entities && metacognition.vague_entities.length > 0 ? (
                                  metacognition.vague_entities.map((node, i) => (
                                    <div key={i} className="bg-slate-950/80 border border-slate-900/60 p-2 rounded flex flex-col gap-1 text-[10px]">
                                      <span className="font-bold text-slate-200">{node.name}</span>
                                      <div className="flex justify-between text-[9px] text-slate-500 mt-1">
                                        <span>{t('metaVagueLinks')}: {node.degree}</span>
                                        <span>{t('metaVagueConfidence')}: {node.confidence.toFixed(2)}</span>
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <div className="col-span-4 text-[10px] text-slate-500 text-center py-4">{t('metaNoVagueConcepts')}</div>
                                )}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-slate-500 text-center py-8">{t('metaWaitingForAssessment')}</div>
                        )}
                      </div>
                    )}

                    {/* Sub-tab 2: Thought Sandbox */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'thought' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="glass-panel border-cyan-950 p-4 flex flex-col gap-3">
                          <h3 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">{t('sandboxMainTitle')}</h3>
                          <p className="text-[10px] leading-relaxed text-slate-400">
                            {t('sandboxMainDesc')}
                          </p>

                          <div className="flex gap-2">
                            <input
                              type="text"
                              placeholder={t('sandboxPlaceholder')}
                              value={hypothesis}
                              onChange={(e) => setHypothesis(e.target.value)}
                              className="cyber-input text-xs flex-1"
                            />
                            <button
                              onClick={runThoughtExperiment}
                              disabled={isThoughtExpLoading || !hypothesis.trim()}
                              className="cyber-btn text-[10px] px-4 font-bold cursor-pointer"
                            >
                              {isThoughtExpLoading ? t('sandboxRunning') : t('sandboxBtn')}
                            </button>
                          </div>
                        </div>

                        {thoughtExpLogs.length > 0 && (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-slide-up">
                            {/* Logs */}
                            <div className="glass-panel p-4 border-slate-900 bg-slate-950/60 flex flex-col gap-2">
                              <span className="text-[10px] text-slate-300 font-bold border-b border-slate-900 pb-1">{t('sandboxLogsTitle')}</span>
                              <div className="flex flex-col gap-1 overflow-y-auto max-h-48 text-[10px] font-mono leading-relaxed text-slate-400">
                                {thoughtExpLogs.map((log, i) => (
                                  <div key={i}>{log}</div>
                                ))}
                              </div>
                            </div>

                            {/* Inferred Hypotheses & Conflicts */}
                            <div className="glass-panel p-4 border-cyan-950 bg-slate-950/60 flex flex-col gap-2">
                              <span className="text-[10px] text-cyan-400 font-bold border-b border-cyan-950 pb-1">{t('sandboxRelationsTitle')}</span>
                              <div className="flex flex-col gap-1.5 overflow-y-auto max-h-48 text-[10px]">
                                {thoughtExpEdges.length > 0 ? (
                                  thoughtExpEdges.map((edge, i) => (
                                    <div key={i} className="bg-cyan-950/40 border border-cyan-900/40 p-2 rounded flex justify-between items-center text-slate-200">
                                      <span>({edge.source} ➔ {edge.relation} ➔ {edge.target})</span>
                                    </div>
                                  ))
                                ) : (
                                  <div className="text-[10px] text-slate-500 text-center py-6">{t('sandboxNoActive')}</div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Sub-tab 3: Socratic Dialogue */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'socratic' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="glass-panel border-purple-950 p-4 flex flex-col gap-3">
                          <h3 className="text-xs font-bold text-purple-400 flex items-center gap-1.5">{t('socraticTitle')}</h3>
                          <p className="text-[10px] leading-relaxed text-slate-400">
                            {t('socraticDesc')}
                          </p>

                          <button
                            onClick={runSocraticDialogue}
                            disabled={isSocraticLoading}
                            className="cyber-btn cyber-btn-emerald text-[10px] py-2 px-6 font-bold self-start cursor-pointer"
                          >
                            {isSocraticLoading ? t('socraticThinking') : t('socraticTriggerBtn')}
                          </button>
                        </div>

                        {socraticDialogue && (
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-slide-up">
                            {/* Dialogue Script */}
                            <div className="glass-panel p-4 md:col-span-2 border-slate-900 bg-slate-950/80 flex flex-col gap-2">
                              <span className="text-[10px] text-purple-400 font-bold border-b border-slate-900 pb-1">{t('socraticScriptTitle')}</span>
                              <div className="text-[11px] leading-relaxed text-slate-300 font-serif whitespace-pre-wrap max-h-96 overflow-y-auto bg-slate-950/60 p-4 rounded-xl border border-slate-900/60">
                                {socraticDialogue}
                              </div>
                            </div>

                            {/* Dialogue Decision Logs */}
                            <div className="glass-panel p-4 border-purple-950 bg-slate-950/80 flex flex-col gap-3">
                              <span className="text-[10px] text-slate-300 font-bold border-b border-slate-950 pb-1">{t('socraticDecisionResultTitle')}</span>
                              <div className="bg-purple-950/30 border border-purple-900/40 p-3 rounded-xl flex flex-col gap-2">
                                <span className="text-[10px] text-slate-400 font-bold">{t('socraticBeliefLabel')}</span>
                                <span className="text-xs font-black text-purple-400">"{socraticBelief}"</span>
                              </div>

                              <div className="bg-slate-950 p-3 rounded-xl border border-slate-900 flex flex-col gap-1 text-[10px]">
                                <span className="text-slate-400 font-bold">{t('socraticDecisionLabel')}</span>
                                <span className={`text-xs font-black mt-1 ${socraticDecision === 'الحذف' || socraticDecision === 'delete' ? 'text-rose-500' : socraticDecision === 'التعديل' || socraticDecision === 'modify' ? 'text-amber-500' : 'text-emerald-500'}`}>
                                  {socraticDecision === 'الحذف' || socraticDecision === 'delete' ? t('socraticDeleteMsg') : socraticDecision === 'التعديل' || socraticDecision === 'modify' ? t('socraticModifyMsg') : t('socraticKeepMsg')}
                                </span>
                              </div>

                              <div className="flex flex-col gap-1 text-[9px] text-slate-500 overflow-y-auto max-h-40">
                                <span className="font-bold mb-1">{t('socraticExecSteps')}</span>
                                {socraticLogs.map((log, i) => (
                                  <div key={i}>{log}</div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Sub-tab 4: Genetic Evolution */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'genetic' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="glass-panel border-purple-950 p-4 flex flex-col gap-3">
                          <h3 className="text-xs font-bold text-purple-400 flex items-center gap-1.5">{t('geneticTitle')}</h3>
                          <p className="text-[10px] leading-relaxed text-slate-400">
                            {t('geneticDesc')}
                          </p>

                          <button
                            onClick={runGeneticRuleEvolution}
                            disabled={isGeneticLoading}
                            className="cyber-btn text-[10px] py-2 px-6 font-bold self-start cursor-pointer"
                          >
                            {isGeneticLoading ? t('geneticRunning') : t('geneticBtn')}
                          </button>
                        </div>

                        {geneticLogs.length > 0 && (
                          <div className="glass-panel p-4 border-slate-900 bg-slate-950/80 flex flex-col gap-2 animate-slide-up">
                            <span className="text-[10px] text-slate-300 font-bold border-b border-slate-900 pb-1">{t('geneticLogsTitle')}</span>
                            <div className="flex flex-col gap-1 overflow-y-auto max-h-60 text-[10px] font-mono leading-relaxed text-slate-400 p-2">
                              {geneticLogs.map((log, i) => (
                                <div key={i} className={log.includes('🧬') ? 'text-purple-400 font-bold' : log.includes('✨') ? 'text-emerald-400 font-black' : ''}>
                                  {log}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Sub-tab 5: Passive Bulk Text Absorption */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'passive' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="glass-panel border-cyan-950 p-4 flex flex-col gap-3">
                          <h3 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">{t('passiveTitle')}</h3>
                          <p className="text-[10px] leading-relaxed text-slate-400">
                            {t('passiveDesc')}
                          </p>

                          <textarea
                            placeholder={t('passivePlaceholder')}
                            value={passiveText}
                            onChange={(e) => setPassiveText(e.target.value)}
                            className="cyber-input h-32 text-xs resize-none bg-slate-950/80 border-slate-800"
                          />

                          <button
                            onClick={runPassiveAbsorption}
                            disabled={isPassiveLoading || !passiveText.trim()}
                            className="cyber-btn text-[10px] px-6 py-2 font-bold self-start cursor-pointer"
                          >
                            {isPassiveLoading ? t('passiveRunning') : t('passiveBtn')}
                          </button>
                        </div>

                        {passiveLogs.length > 0 && (
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-slide-up">
                            {/* Stats */}
                            <div className="glass-panel p-4 border-cyan-950 flex flex-col justify-center items-center text-center gap-2">
                              <span className="text-[10px] text-slate-400 font-bold">{t('passiveMergedLabel')}</span>
                              <span className="text-2xl font-black text-cyan-400">+{passiveAbsorbed}</span>
                              <span className="text-[9px] text-slate-500">{t('passiveMergedDesc')}</span>
                            </div>
                            <div className="glass-panel p-4 border-rose-950 flex flex-col justify-center items-center text-center gap-2">
                              <span className="text-[10px] text-slate-400 font-bold">{t('passiveContradictionsLabel')}</span>
                              <span className="text-2xl font-black text-rose-400">{passiveContradictions}</span>
                              <span className="text-[9px] text-slate-500">{t('passiveContradictionsDesc')}</span>
                            </div>

                            {/* Logs list */}
                            <div className="glass-panel p-4 md:col-span-3 border-slate-900 bg-slate-950/80 flex flex-col gap-2">
                              <span className="text-[10px] text-slate-300 font-bold border-b border-slate-900 pb-1">{t('passiveLogsTitle')}</span>
                              <div className="flex flex-col gap-1 overflow-y-auto max-h-48 text-[10px] font-mono leading-relaxed text-slate-400 p-1">
                                {passiveLogs.map((log, i) => (
                                  <div key={i}>{log}</div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Sub-tab 6: Workspace Diff */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'diff' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="glass-panel border-cyan-950 p-4 flex flex-col gap-3">
                          <h3 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">{t('diffTitle')}</h3>
                          <p className="text-[10px] leading-relaxed text-slate-400">
                            {t('diffDesc')}
                          </p>

                          <div className="flex gap-2">
                            <select
                              value={diffWorkspaceName}
                              onChange={(e) => setDiffWorkspaceName(e.target.value)}
                              className="cyber-input text-xs flex-1 bg-slate-950"
                            >
                              <option value="">{t('diffSelectPlaceholder')}</option>
                              {Object.keys(workspaces).filter(w => w !== currentWorkspace).map(w => (
                                <option key={w} value={w}>{w === 'العقل العام (الافتراضي)' ? t('defaultWorkspaceName') : w}</option>
                              ))}
                            </select>

                            <button
                              onClick={runWorkspaceDiff}
                              disabled={isDiffLoading || !diffWorkspaceName}
                              className="cyber-btn text-[10px] px-6 font-bold cursor-pointer"
                            >
                              {isDiffLoading ? t('diffRunning') : t('diffBtn')}
                            </button>
                          </div>
                        </div>

                        {workspaceDiff && (
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs animate-slide-up">
                            {/* Added */}
                            <div className="glass-panel p-4 border-emerald-950 bg-slate-950/60 flex flex-col gap-2">
                              <span className="text-[10px] text-emerald-400 font-bold border-b border-emerald-900 pb-1">{t('diffAddedTitle')}</span>
                              <div className="flex flex-col gap-1 overflow-y-auto max-h-48 text-[10px]">
                                {workspaceDiff.added_concepts && workspaceDiff.added_concepts.map((c, i) => (
                                  <div key={i} className="text-emerald-400 font-bold bg-emerald-950/30 p-1 rounded">{t('concept')}: [{c}]</div>
                                ))}
                                {workspaceDiff.added_triples && workspaceDiff.added_triples.map((t, i) => (
                                  <div key={i} className="text-emerald-300 bg-emerald-950/20 p-1.5 rounded leading-tight">({t.subject} ➔ {t.predicate} ➔ {t.object})</div>
                                ))}
                                {(!workspaceDiff.added_concepts?.length && !workspaceDiff.added_triples?.length) && (
                                  <div className="text-slate-500 text-center py-4">{t('diffNoAdded')}</div>
                                )}
                              </div>
                            </div>

                            {/* Deleted */}
                            <div className="glass-panel p-4 border-rose-950 bg-slate-950/60 flex flex-col gap-2">
                              <span className="text-[10px] text-rose-400 font-bold border-b border-rose-900 pb-1">{t('diffDeletedTitle')}</span>
                              <div className="flex flex-col gap-1 overflow-y-auto max-h-48 text-[10px]">
                                {workspaceDiff.deleted_concepts && workspaceDiff.deleted_concepts.map((c, i) => (
                                  <div key={i} className="text-rose-400 font-bold bg-rose-950/30 p-1 rounded">{t('concept')}: [{c}]</div>
                                ))}
                                {workspaceDiff.deleted_triples && workspaceDiff.deleted_triples.map((t, i) => (
                                  <div key={i} className="text-rose-300 bg-rose-950/20 p-1.5 rounded leading-tight">({t.subject} ➔ {t.predicate} ➔ {t.object})</div>
                                ))}
                                {(!workspaceDiff.deleted_concepts?.length && !workspaceDiff.deleted_triples?.length) && (
                                  <div className="text-slate-500 text-center py-4">{t('diffNoDeleted')}</div>
                                )}
                              </div>
                            </div>

                            {/* Conflicts */}
                            <div className="glass-panel p-4 border-amber-950 bg-slate-950/60 flex flex-col gap-2">
                              <span className="text-[10px] text-amber-400 font-bold border-b border-amber-900 pb-1">{t('diffConflictsTitle')}</span>
                              <div className="flex flex-col gap-1 overflow-y-auto max-h-48 text-[10px]">
                                {workspaceDiff.conflicting_triples && workspaceDiff.conflicting_triples.map((t, i) => (
                                  <div key={i} className="bg-amber-950/20 border border-amber-900/40 p-2 rounded flex flex-col gap-1 leading-tight text-slate-200">
                                    <span>{t('diffCommonRelation')} {t.subject} ➔ {t.object}</span>
                                    <div className="flex justify-between text-[9px] text-slate-400 mt-1">
                                      <span>{t('diffCurrentVal')} "{t.predicate_current}"</span>
                                      <span className="text-amber-400">{t('diffOtherVal')} "{t.predicate_other}"</span>
                                    </div>
                                  </div>
                                ))}
                                {!workspaceDiff.conflicting_triples?.length && (
                                  <div className="text-slate-500 text-center py-4">{t('diffNoConflicts')}</div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Sub-tab 7: Procedural Knowledge Chains */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'procedural' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Create Procedure */}
                          <div className="glass-panel border-cyan-950 p-4 flex flex-col gap-3">
                            <h3 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">{t('procTitle')}</h3>
                            <p className="text-[10px] leading-relaxed text-slate-400">
                              {t('procDesc')}
                            </p>

                            <div className="flex flex-col gap-2">
                              <input
                                type="text"
                                placeholder={t('procNamePlaceholder')}
                                value={newProcedureName}
                                onChange={(e) => setNewProcedureName(e.target.value)}
                                className="cyber-input text-xs"
                              />

                              <textarea
                                placeholder={t('procStepsPlaceholder')}
                                value={newProcedureSteps}
                                onChange={(e) => setNewProcedureSteps(e.target.value)}
                                className="cyber-input h-32 text-xs resize-none"
                              />

                              <label className="flex items-center gap-2 text-[10px] text-slate-300 select-none cursor-pointer my-1 font-bold">
                                <input
                                  type="checkbox"
                                  checked={isProcedureGlobal}
                                  onChange={(e) => setIsProcedureGlobal(e.target.checked)}
                                  className="w-3.5 h-3.5 accent-cyan-500 rounded border-slate-900 bg-slate-950 cursor-pointer"
                                />
                                <span>{t('procGlobalLabel')}</span>
                              </label>

                              <button
                                onClick={addProceduralChain}
                                disabled={isProceduralLoading || !newProcedureName || !newProcedureSteps}
                                className="cyber-btn text-[10px] px-6 py-2 font-bold self-start cursor-pointer"
                              >
                                {isProceduralLoading ? t('procRunning') : t('procBtn')}
                              </button>
                            </div>
                          </div>

                          {/* List Stored Procedures */}
                          <div className="glass-panel border-slate-900 bg-slate-950/60 p-4 flex flex-col gap-3">
                            <h3 className="text-xs font-bold text-slate-200 border-b border-slate-900 pb-2 flex items-center gap-1.5">{t('procListTitle')}</h3>
                            <div className="flex flex-col gap-3 overflow-y-auto max-h-96">
                              {Object.keys(procedures).length > 0 ? (
                                Object.entries(procedures).map(([name, steps], i) => (
                                  <div key={i} className="bg-slate-950 p-3 rounded-xl border border-slate-900 flex flex-col gap-2 animate-slide-up">
                                    <span className="text-xs font-black text-cyan-400">⚙️ {name}</span>
                                    <div className="flex flex-col gap-1 pl-2 border-l border-cyan-900/40">
                                      {steps.map((step, idx) => (
                                        <div key={idx} className="flex gap-2 text-[10px] leading-relaxed text-slate-300">
                                          <span className="text-cyan-600 font-mono font-bold">{idx + 1}.</span>
                                          <span>{step}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <div className="text-[10px] text-slate-500 text-center py-12">{t('procEmptyList')}</div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Sub-tab 8: Federated Simulated P2P Intelligence */}
                    {(localStorage.getItem('legend_advanced_subtab') || 'metacognition') === 'federated' && (
                      <div className="slide-in flex flex-col gap-4">
                        <div className="glass-panel border-cyan-950 p-4 flex flex-col gap-3">
                          <h3 className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">{t('fedTitle')}</h3>
                          <p className="text-[10px] leading-relaxed text-slate-400">
                            {t('fedDesc')}
                          </p>

                          <div className="flex gap-2">
                            <input
                              type="text"
                              placeholder={t('fedPlaceholder')}
                              value={federatedQuery}
                              onChange={(e) => setFederatedQuery(e.target.value)}
                              className="cyber-input text-xs flex-1"
                            />

                            <button
                              onClick={runFederatedSimulate}
                              disabled={isFederatedLoading || !federatedQuery}
                              className="cyber-btn text-[10px] px-6 font-bold cursor-pointer"
                            >
                              {isFederatedLoading ? t('fedRunning') : t('fedBtn')}
                            </button>
                          </div>
                        </div>

                        {federatedLogs.length > 0 && (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-slide-up">
                            {/* Peer results */}
                            <div className="glass-panel p-4 border-cyan-950 bg-slate-950/80 flex flex-col gap-2">
                              <span className="text-[10px] text-cyan-400 font-bold border-b border-cyan-950 pb-1">{t('fedInboundTitle', { federatedPeer })}</span>
                              <div className="flex flex-col gap-2 overflow-y-auto max-h-60 text-[11px] text-slate-200">
                                {federatedConcepts.map((c, i) => (
                                  <div key={i} className="bg-slate-900 border border-slate-800 p-1.5 rounded flex items-center justify-between text-xs">
                                    <span className="font-bold text-slate-200">{t('fedReceivedConcept')} [{c}]</span>
                                  </div>
                                ))}
                                {federatedTriples.map((t, i) => (
                                  <div key={i} className="bg-slate-900 border border-slate-800 p-2 rounded flex flex-col gap-1 leading-tight text-xs">
                                    <span>({t.subject} ➔ {t.predicate} ➔ {t.object})</span>
                                    <span className="text-[9px] text-cyan-400 font-bold self-end mt-1">{t('fedTrustConfidence')} {t.confidence}</span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* P2P network sync logs */}
                            <div className="glass-panel p-4 border-slate-900 bg-slate-950/80 flex flex-col gap-2">
                              <span className="text-[10px] text-slate-300 font-bold border-b border-slate-900 pb-1">{t('fedLogsTitle')}</span>
                              <div className="flex flex-col gap-1 overflow-y-auto max-h-60 text-[10px] font-mono leading-relaxed text-slate-400">
                                {federatedLogs.map((log, i) => (
                                  <div key={i}>{log}</div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 8: Interactive Concept Documentation Guide */}
              {activeTab === 'documentation' && (
                <div className="slide-in flex flex-col gap-5 h-full p-3 overflow-y-auto">
                  <div className="glass-panel border-cyan-950 bg-gradient-to-l from-cyan-950/10 via-[#070913] to-[#070913] p-5 rounded-2xl flex flex-col gap-2">
                    <h3 className="text-sm font-black text-cyan-400 flex items-center gap-2 border-b border-cyan-950/40 pb-2">
                      <BookOpen className="w-5 h-5 text-cyan-400 animate-pulse" />
                      {t('guideMainTitle')}
                    </h3>
                    <p className="text-xs leading-relaxed text-slate-300 leading-relaxed">
                      {t('guideMainDesc')}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Concept 1 */}
                    <div className="glass-panel p-4 border-cyan-900/60 bg-slate-950/40 flex flex-col gap-3">
                      <h4 className="text-xs font-black text-cyan-400 flex items-center gap-1.5 border-b border-slate-900 pb-1">
                        {t('guideConcept1Title')}
                      </h4>
                      <p className="text-[10px] leading-relaxed text-slate-400">
                        {t('guideConcept1Desc')}
                      </p>
                      <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-900 font-mono text-[9px] text-slate-400 leading-tight">
                        +---------------------------------------+<br />
                        |  {t('guideConcept1Diagram1')}  |<br />
                        +---------------------------------------+<br />
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;| {t('guideConcept1Diagram2')}<br />
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v<br />
                        +---------------------------------------+<br />
                        | {t('guideConcept1Diagram3')} |<br />
                        +---------------------------------------+
                      </div>
                    </div>

                    {/* Concept 2 */}
                    <div className="glass-panel p-4 border-purple-900/60 bg-slate-950/40 flex flex-col gap-3">
                      <h4 className="text-xs font-black text-purple-400 flex items-center gap-1.5 border-b border-slate-900 pb-1">
                        {t('guideConcept2Title')}
                      </h4>
                      <p className="text-[10px] leading-relaxed text-slate-400">
                        {t('guideConcept2Desc')}
                      </p>
                      <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-900 font-mono text-[9px] text-slate-400 leading-tight">
                        {t('guideConcept2Example1')}<br />
                        {t('guideConcept2Example2')}<br />
                        {t('guideConcept2Example3')}
                      </div>
                    </div>

                    {/* Concept 3 */}
                    <div className="glass-panel p-4 border-amber-900/60 bg-slate-950/40 flex flex-col gap-3">
                      <h4 className="text-xs font-black text-amber-400 flex items-center gap-1.5 border-b border-slate-900 pb-1">
                        {t('guideConcept3Title')}
                      </h4>
                      <p className="text-[10px] leading-relaxed text-slate-400">
                        {t('guideConcept3Desc')}
                      </p>
                      <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-900 font-mono text-[9px] text-slate-400 leading-tight">
                        {t('guideConcept3Step1')}<br />
                        {t('guideConcept3Step2')}<br />
                        {t('guideConcept3Step3')}
                      </div>
                    </div>

                    {/* Concept 4 */}
                    <div className="glass-panel p-4 border-rose-900/60 bg-slate-950/40 flex flex-col gap-3">
                      <h4 className="text-xs font-black text-rose-400 flex items-center gap-1.5 border-b border-slate-900 pb-1">
                        {t('guideConcept4Title')}
                      </h4>
                      <p className="text-[10px] leading-relaxed text-slate-400">
                        {t('guideConcept4Desc')}
                      </p>
                      <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-900 font-mono text-[9px] text-slate-400 leading-tight">
                        {t('guideConcept4Step1')}<br />
                        {t('guideConcept4Step2')}<br />
                        {t('guideConcept4Step3')}
                      </div>
                    </div>

                    {/* Concept 5 */}
                    <div className="glass-panel p-4 border-emerald-900/60 bg-slate-950/40 flex flex-col gap-3">
                      <h4 className="text-xs font-black text-emerald-400 flex items-center gap-1.5 border-b border-slate-900 pb-1">
                        {t('guideConcept5Title')}
                      </h4>
                      <p className="text-[10px] leading-relaxed text-slate-400">
                        {t('guideConcept5Desc')}
                      </p>
                    </div>

                    {/* Concept 6 */}
                    <div className="glass-panel p-4 border-indigo-900/60 bg-slate-950/40 flex flex-col gap-3">
                      <h4 className="text-xs font-black text-indigo-400 flex items-center gap-1.5 border-b border-slate-900 pb-1">
                        {t('guideConcept6Title')}
                      </h4>
                      <p className="text-[10px] leading-relaxed text-slate-400">
                        {t('guideConcept6Desc')}
                      </p>
                      <ul className="text-[9px] list-disc list-inside text-slate-400 leading-normal flex flex-col gap-1 pr-1" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
                        <li>{t('guideConcept6Bullet1')}</li>
                        <li>{t('guideConcept6Bullet2')}</li>
                        <li>{t('guideConcept6Bullet3')}</li>
                      </ul>
                      <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-900 font-mono text-[9px] text-slate-400 leading-tight">
                        {t('guideConcept6FormulaTitle')}<br />
                        {t('guideConcept6FormulaAntecedents')}<br />
                        {t('guideConcept6FormulaConsequent')}
                      </div>
                    </div>

                    {/* Concept 7 */}
                    <div className="glass-panel p-4 border-cyan-800 bg-slate-950/40 flex flex-col gap-3 col-span-1 md:col-span-2">
                      <div className="flex items-center justify-between border-b border-slate-900 pb-2">
                        <h4 className="text-xs font-black text-cyan-400 flex items-center gap-1.5">
                          {t('guideConcept7Title')}
                        </h4>
                        <button
                          onClick={async () => {
                            navigator.clipboard.writeText(t('cognitivePrompt'));
                            if (typeof addLog === 'function') {
                              addLog(t('promptCopySuccess'), "success");
                            } else {
                              await showAlert(t('promptCopySuccess'));
                            }
                          }}
                          className="px-2.5 py-1 hover:bg-cyan-950/60 rounded border border-cyan-900/40 text-cyan-400 hover:text-cyan-300 transition flex items-center gap-1.5 active:scale-95 cursor-pointer text-[10px] font-bold"
                        >
                          <Copy className="w-3.5 h-3.5" />
                          {t('guideCopyPromptBtn')}
                        </button>
                      </div>
                      <p className="text-[10px] leading-relaxed text-slate-300">
                        {t('guideConcept7Desc')}
                      </p>
                      <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-900 font-mono text-[9px] text-slate-400 whitespace-pre-wrap leading-relaxed select-all" style={{ direction: 'ltr' }}>
                        {t('cognitivePrompt')}
                      </div>
                    </div>

                  </div>
                </div>
              )}

            </div>
          </section>
        </main>
      </div>

      {/* 3. New Workspace modal popup */}
      {isWorkspaceModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md bg-[#070913] border border-cyan-900 rounded-2xl p-6 shadow-2xl flex flex-col gap-4 slide-in">
            <h3 className="text-sm font-black text-cyan-400 flex items-center gap-1.5">
              <Plus className="w-5 h-5 animate-spin" />
              {t('modalWsTitle')}
            </h3>
            
            <form onSubmit={handleCreateWorkspace} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs text-slate-400">{t('modalWsNameLabel')}</label>
                <input 
                  type="text" 
                  placeholder={t('modalWsNamePlaceholder')}
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  className="cyber-input text-xs"
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs text-slate-400">{t('modalWsModeLabel')}</label>
                
                <div className="flex flex-col gap-2 mt-1">
                  <label className="flex items-center gap-2 bg-slate-950/50 p-2.5 rounded-lg border border-slate-900 cursor-pointer">
                    <input 
                      type="radio" 
                      name="ws_mode" 
                      value="active"
                      checked={newWsMode === 'active'}
                      onChange={() => setNewWsMode('active')}
                      className="accent-purple-500"
                    />
                    <div className="flex flex-col">
                      <span className="text-[11px] font-bold text-slate-200">{t('modalWsModeActiveTitle')}</span>
                      <span className="text-[9px] text-slate-500">{t('modalWsModeActiveDesc')}</span>
                    </div>
                  </label>

                  <label className="flex items-center gap-2 bg-slate-950/50 p-2.5 rounded-lg border border-slate-900 cursor-pointer">
                    <input 
                      type="radio" 
                      name="ws_mode" 
                      value="strict"
                      checked={newWsMode === 'strict'}
                      onChange={() => setNewWsMode('strict')}
                      className="accent-rose-500"
                    />
                    <div className="flex flex-col">
                      <span className="text-[11px] font-bold text-slate-200">{t('modalWsModeStrictTitle')}</span>
                      <span className="text-[9px] text-slate-500">{t('modalWsModeStrictDesc')}</span>
                    </div>
                  </label>
                </div>
              </div>

              <div className="flex gap-2 justify-end mt-2">
                <button 
                  type="button" 
                  onClick={() => setIsWorkspaceModalOpen(false)}
                  className="cyber-btn-secondary text-xs py-1.5 px-4 font-bold"
                >
                  {t('modalWsCancelBtn')}
                </button>
                <button 
                  type="submit"
                  className="cyber-btn text-xs py-1.5 px-4 font-bold"
                >
                  {t('modalWsCreateBtn')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {currentProgress && (
        <div className="fixed bottom-6 right-6 z-50 w-80 bg-slate-950/85 backdrop-blur-md border border-cyan-500/40 rounded-2xl p-4 shadow-[0_0_25px_rgba(6,182,212,0.25)] slide-in flex flex-col gap-3" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
          <div className="flex items-center justify-between border-b border-slate-900 pb-2">
            <span className="text-[11px] font-black text-cyan-400 flex items-center gap-1.5 animate-pulse">
              <Activity className="w-3.5 h-3.5 animate-spin text-cyan-400" />
              {currentProgress.process_name || t('progressDefaultTitle')}
            </span>
            <span className="text-[9px] font-mono text-cyan-400 bg-cyan-950/50 border border-cyan-900/60 px-2 py-0.5 rounded-md font-bold" style={{ direction: 'ltr' }}>
              ⏱️ {currentProgress.elapsed_seconds || 0.0}s
            </span>
          </div>
          
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] text-slate-200 font-bold leading-relaxed">
              {currentProgress.phase || t('progressDefaultPhase')}
            </span>
            {currentProgress.total > 0 && (
              <div className="flex justify-between text-[9px] text-slate-400 mt-1">
                <span>{t('progressSuccessLabel')}</span>
                <span className="font-mono font-bold text-cyan-400">
                  {currentProgress.current} / {currentProgress.total} ({Math.round((currentProgress.current / currentProgress.total) * 100)}%)
                </span>
              </div>
            )}
          </div>

          {currentProgress.total > 0 && (
            <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800/80">
              <div 
                className="bg-gradient-to-r from-cyan-500 to-blue-500 h-full rounded-full transition-all duration-300 shadow-[0_0_8px_rgba(6,182,212,0.4)]"
                style={{ width: `${(currentProgress.current / currentProgress.total) * 100}%` }}
              />
            </div>
          )}

          <button 
            type="button"
            onClick={handleAbort}
            className="mt-1 flex items-center justify-center gap-1.5 py-1 px-3 rounded-lg border border-rose-500/30 hover:border-rose-500/70 bg-rose-950/20 hover:bg-rose-950/40 text-rose-400 hover:text-rose-350 text-[10px] font-bold transition-all duration-200 active:scale-95 shadow-[0_0_8px_rgba(244,63,94,0.05)] hover:shadow-[0_0_12px_rgba(244,63,94,0.2)]"
          >
            <XCircle className="w-3.5 h-3.5 text-rose-500 group-hover:animate-pulse" />
            {language === 'ar' ? 'إلغاء وإيقاف الحفظ' : 'Cancel & Stop Ingestion'}
          </button>
        </div>
      )}

      {/* Premium Sci-Fi Promise-Based Dialog Modal */}
      {customModal.isOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
          <div 
            className={`w-full max-w-md glass-panel p-6 rounded-2xl border flex flex-col gap-5 shadow-[0_0_50px_rgba(0,0,0,0.8)] transition-all duration-300 transform scale-100 opacity-100 ${
              customModal.isDestructive 
                ? 'border-rose-900/60 bg-slate-950/90 shadow-[0_0_40px_rgba(244,63,94,0.15)] text-rose-50'
                : 'border-cyan-900/60 bg-slate-950/90 shadow-[0_0_40px_rgba(6,182,212,0.15)] text-cyan-50'
            }`}
            style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}
          >
            <div className="flex items-start gap-4">
              <div className={`p-3 rounded-xl border shrink-0 ${
                customModal.isDestructive
                  ? 'bg-rose-950/40 border-rose-800/50 text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.2)]'
                  : 'bg-cyan-950/40 border-cyan-800/50 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.2)]'
              }`}>
                <AlertTriangle className="w-6 h-6 animate-pulse" />
              </div>
              <div className="flex-1 flex flex-col gap-1.5 min-w-0">
                <h3 className={`text-sm font-black tracking-wide uppercase ${
                  customModal.isDestructive ? 'text-rose-400' : 'text-cyan-400'
                }`}>
                  {customModal.title}
                </h3>
                <p className="text-xs leading-relaxed text-slate-300 font-medium whitespace-pre-wrap">
                  {customModal.message}
                </p>
              </div>
            </div>

            <div className={`flex items-center gap-3 mt-2 ${
              language === 'ar' ? 'justify-start' : 'justify-end'
            }`}>
              {customModal.type === 'confirm' && (
                <button
                  onClick={handleModalCancel}
                  className="px-4 py-2 hover:bg-slate-900 rounded-xl border border-slate-800/80 text-slate-400 hover:text-slate-200 transition text-xs font-bold active:scale-95 cursor-pointer"
                >
                  {customModal.cancelLabel}
                </button>
              )}
              <button
                onClick={handleModalConfirm}
                className={`px-5 py-2 rounded-xl text-xs font-black transition active:scale-95 cursor-pointer shadow-lg ${
                  customModal.isDestructive
                    ? 'bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white shadow-rose-950/50 hover:shadow-rose-900/60'
                    : 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-slate-950 shadow-cyan-950/50 hover:shadow-cyan-900/60 font-black'
                }`}
              >
                {customModal.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default App;
