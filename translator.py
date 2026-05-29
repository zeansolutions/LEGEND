import json
import re

class LogTranslator:
    def __init__(self, translations_file):
        with open(translations_file, "r", encoding="utf-8") as f:
            self.translations = json.load(f)
            
        self.ar_dict = self.translations.get("ar", {})
        self.patterns = []
        self.exact_matches = {}
        
        for key, template in self.ar_dict.items():
            if '{' in template:
                # Create regex pattern
                pattern_str = re.escape(template)
                # Replace escaped \{xxx\} with (.*?)
                keys = re.findall(r'\{(.*?)\}', template)
                for k in keys:
                    pattern_str = pattern_str.replace(r'\{' + k + r'\}', r'(.*?)', 1)
                
                regex = re.compile("^" + pattern_str + "$")
                self.patterns.append({
                    "key": key,
                    "regex": regex,
                    "keys": keys
                })
            else:
                self.exact_matches[template] = key
                
    def translate(self, text, lang="en"):
        if lang == "ar":
            return text
            
        lang_dict = self.translations.get(lang) or self.translations.get("en", {})
        
        # Check exact matches first
        if text in self.exact_matches:
            key = self.exact_matches[text]
            return lang_dict.get(key) or self.translations["en"].get(key, text)
            
        # Check regex matches
        for p in self.patterns:
            match = p["regex"].match(text)
            if match:
                key = p["key"]
                template = lang_dict.get(key) or self.translations["en"].get(key)
                if not template:
                    return text
                    
                # Replace kwargs
                values = match.groups()
                for i, k in enumerate(p["keys"]):
                    template = template.replace(f"{{{k}}}", values[i])
                return template
                
        return text

class TranslatableLogList(list):
    def __init__(self, lang, translator):
        super().__init__()
        self.lang = lang
        self.translator = translator

    def append(self, item):
        super().append(self.translator.translate(item, self.lang))

# Test
if __name__ == "__main__":
    t = LogTranslator("python_translations.json")
    print(t.translate("🧠 [تعلم تراكمي]: إدراج مفهوم جديد 'قطة' ➔ تصنيفه: 'حيوان' بـثقة 0.95", "en"))
