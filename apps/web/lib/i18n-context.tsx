"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

/* ──────────────────────────────────────────────────────────────────────
 * Supported Indian languages (22 Scheduled Languages + English)
 * ────────────────────────────────────────────────────────────────────── */
export const SUPPORTED_LANGUAGES = [
  { code: "en",  label: "English",     nativeLabel: "English" },
  { code: "hi",  label: "Hindi",       nativeLabel: "हिन्दी" },
  { code: "bn",  label: "Bengali",     nativeLabel: "বাংলা" },
  { code: "te",  label: "Telugu",      nativeLabel: "తెలుగు" },
  { code: "mr",  label: "Marathi",     nativeLabel: "मराठी" },
  { code: "ta",  label: "Tamil",       nativeLabel: "தமிழ்" },
  { code: "gu",  label: "Gujarati",    nativeLabel: "ગુજરાતી" },
  { code: "kn",  label: "Kannada",     nativeLabel: "ಕನ್ನಡ" },
  { code: "ml",  label: "Malayalam",   nativeLabel: "മലയാളം" },
  { code: "or",  label: "Odia",        nativeLabel: "ଓଡ଼ିଆ" },
  { code: "pa",  label: "Punjabi",     nativeLabel: "ਪੰਜਾਬੀ" },
  { code: "as",  label: "Assamese",    nativeLabel: "অসমীয়া" },
  { code: "mai", label: "Maithili",    nativeLabel: "मैथिली" },
  { code: "sa",  label: "Sanskrit",    nativeLabel: "संस्कृतम्" },
  { code: "ne",  label: "Nepali",      nativeLabel: "नेपाली" },
  { code: "sd",  label: "Sindhi",      nativeLabel: "سنڌي" },
  { code: "ks",  label: "Kashmiri",    nativeLabel: "कॉशुर" },
  { code: "kok", label: "Konkani",     nativeLabel: "कोंकणी" },
  { code: "doi", label: "Dogri",       nativeLabel: "डोगरी" },
  { code: "mni", label: "Manipuri",    nativeLabel: "মৈতৈলোন্" },
  { code: "bo",  label: "Bodo",        nativeLabel: "बड़ो" },
  { code: "sat", label: "Santali",     nativeLabel: "ᱥᱟᱱᱛᱟᱲᱤ" },
  { code: "ur",  label: "Urdu",        nativeLabel: "اردو" },
] as const;

export type LangCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

/* ──────────────────────────────────────────────────────────────────────
 * Translation strings
 * ────────────────────────────────────────────────────────────────────── */
type TranslationKeys =
  | "appName"
  | "appTagline"
  | "signIn"
  | "signUp"
  | "email"
  | "password"
  | "fullName"
  | "role"
  | "state"
  | "signingIn"
  | "creatingAccount"
  | "createAccount"
  | "newToBhoomi"
  | "alreadyHaveAccount"
  | "loading"
  | "overview"
  | "myFarms"
  | "intelligence"
  | "cropDoctor"
  | "cooperation"
  | "advisories"
  | "settings"
  | "admin"
  | "notifications"
  | "noNotifications"
  | "logOut"
  | "farmer"
  | "agronomist"
  | "language"
  | "disclaimer";

type Translations = Record<TranslationKeys, string>;

// `noUncheckedIndexedAccess` widens `Record<string, ...>` lookups to include
// `undefined`, so pin English as a required key and treat every other locale as
// partial (falling back key-by-key in `t`).
const translations: { en: Translations } & Record<string, Partial<Translations>> = {
  en: {
    appName: "BHOOMI",
    appTagline: "Agriculture Intelligence Platform",
    signIn: "Sign in",
    signUp: "Create your account",
    email: "Email",
    password: "Password",
    fullName: "Full name",
    role: "Role",
    state: "State (optional)",
    signingIn: "Signing in…",
    creatingAccount: "Creating account…",
    createAccount: "Create account",
    newToBhoomi: "New to BHOOMI?",
    alreadyHaveAccount: "Already have an account?",
    loading: "Loading BHOOMI…",
    overview: "Overview",
    myFarms: "My Farms",
    intelligence: "Intelligence",
    cropDoctor: "Crop Doctor",
    cooperation: "Cooperation",
    advisories: "Advisories",
    settings: "Settings",
    admin: "Admin",
    notifications: "Notifications",
    noNotifications: "No notifications yet.",
    logOut: "Log out",
    farmer: "Farmer",
    agronomist: "Agronomist",
    language: "Language",
    disclaimer:
      "BHOOMI Intelligence Score is an internal composite index, not an official agricultural standard.",
  },
  hi: {
    appName: "भूमि",
    appTagline: "कृषि बुद्धिमत्ता मंच",
    signIn: "साइन इन करें",
    signUp: "अपना खाता बनाएं",
    email: "ईमेल",
    password: "पासवर्ड",
    fullName: "पूरा नाम",
    role: "भूमिका",
    state: "राज्य (वैकल्पिक)",
    signingIn: "साइन इन हो रहा है…",
    creatingAccount: "खाता बनाया जा रहा है…",
    createAccount: "खाता बनाएं",
    newToBhoomi: "भूमि पर नए हैं?",
    alreadyHaveAccount: "पहले से खाता है?",
    loading: "भूमि लोड हो रहा है…",
    overview: "अवलोकन",
    myFarms: "मेरे खेत",
    intelligence: "बुद्धिमत्ता",
    cropDoctor: "फसल चिकित्सक",
    cooperation: "सहयोग",
    advisories: "सलाह",
    settings: "सेटिंग्स",
    admin: "एडमिन",
    notifications: "सूचनाएं",
    noNotifications: "अभी तक कोई सूचना नहीं।",
    logOut: "लॉग आउट",
    farmer: "किसान",
    agronomist: "कृषि विज्ञानी",
    language: "भाषा",
    disclaimer:
      "भूमि बुद्धिमत्ता स्कोर एक आंतरिक समग्र सूचकांक है, कोई आधिकारिक कृषि मानक नहीं।",
  },
  bn: {
    appName: "ভূমি",
    appTagline: "কৃষি বুদ্ধিমত্তা প্ল্যাটফর্ম",
    signIn: "সাইন ইন করুন",
    signUp: "আপনার অ্যাকাউন্ট তৈরি করুন",
    email: "ইমেইল",
    password: "পাসওয়ার্ড",
    fullName: "পুরো নাম",
    role: "ভূমিকা",
    state: "রাজ্য (ঐচ্ছিক)",
    signingIn: "সাইন ইন হচ্ছে…",
    creatingAccount: "অ্যাকাউন্ট তৈরি হচ্ছে…",
    createAccount: "অ্যাকাউন্ট তৈরি করুন",
    newToBhoomi: "ভূমিতে নতুন?",
    alreadyHaveAccount: "ইতিমধ্যে অ্যাকাউন্ট আছে?",
    loading: "ভূমি লোড হচ্ছে…",
    overview: "সংক্ষিপ্ত বিবরণ",
    myFarms: "আমার খামার",
    intelligence: "বুদ্ধিমত্তা",
    cropDoctor: "ফসল ডাক্তার",
    cooperation: "সহযোগিতা",
    advisories: "পরামর্শ",
    settings: "সেটিংস",
    admin: "অ্যাডমিন",
    notifications: "বিজ্ঞপ্তি",
    noNotifications: "এখনও কোনো বিজ্ঞপ্তি নেই।",
    logOut: "লগ আউট",
    farmer: "কৃষক",
    agronomist: "কৃষি বিজ্ঞানী",
    language: "ভাষা",
    disclaimer:
      "ভূমি বুদ্ধিমত্তা স্কোর একটি অভ্যন্তরীণ সংমিশ্র সূচক, কোনো সরকারি কৃষি মানদণ্ড নয়।",
  },
  te: {
    appName: "భూమి",
    appTagline: "వ్యవసాయ మేధస్సు వేదిక",
    signIn: "సైన్ ఇన్ చేయండి",
    signUp: "మీ ఖాతాను సృష్టించండి",
    email: "ఇమెయిల్",
    password: "పాస్‌వర్డ్",
    fullName: "పూర్తి పేరు",
    role: "పాత్ర",
    state: "రాష్ట్రం (ఐచ్ఛికం)",
    signingIn: "సైన్ ఇన్ అవుతోంది…",
    creatingAccount: "ఖాతా సృష్టించబడుతోంది…",
    createAccount: "ఖాతా సృష్టించండి",
    newToBhoomi: "భూమికి కొత్తా?",
    alreadyHaveAccount: "ఇప్పటికే ఖాతా ఉందా?",
    loading: "భూమి లోడ్ అవుతోంది…",
    overview: "అవలోకనం",
    myFarms: "నా పొలాలు",
    intelligence: "మేధస్సు",
    cropDoctor: "పంట వైద్యుడు",
    cooperation: "సహకారం",
    advisories: "సలహాలు",
    settings: "సెట్టింగ్‌లు",
    admin: "అడ్మిన్",
    notifications: "నోటిఫికేషన్‌లు",
    noNotifications: "ఇంకా నోటిఫికేషన్‌లు లేవు.",
    logOut: "లాగ్ అవుట్",
    farmer: "రైతు",
    agronomist: "వ్యవసాయ శాస్త్రవేత్త",
    language: "భాష",
    disclaimer:
      "భూమి మేధస్సు స్కోర్ అనేది అంతర్గత సమగ్ర సూచిక, అధికారిక వ్యవసాయ ప్రమాణం కాదు.",
  },
  mr: {
    appName: "भूमी",
    appTagline: "कृषी बुद्धिमत्ता व्यासपीठ",
    signIn: "साइन इन करा",
    signUp: "तुमचे खाते तयार करा",
    email: "ईमेल",
    password: "पासवर्ड",
    fullName: "पूर्ण नाव",
    role: "भूमिका",
    state: "राज्य (पर्यायी)",
    signingIn: "साइन इन होत आहे…",
    creatingAccount: "खाते तयार होत आहे…",
    createAccount: "खाते तयार करा",
    newToBhoomi: "भूमीवर नवीन आहात?",
    alreadyHaveAccount: "आधीच खाते आहे?",
    loading: "भूमी लोड होत आहे…",
    overview: "आढावा",
    myFarms: "माझी शेती",
    intelligence: "बुद्धिमत्ता",
    cropDoctor: "पीक डॉक्टर",
    cooperation: "सहकार्य",
    advisories: "सल्ला",
    settings: "सेटिंग्ज",
    admin: "ॲडमिन",
    notifications: "सूचना",
    noNotifications: "अद्याप कोणत्याही सूचना नाहीत.",
    logOut: "लॉग आउट",
    farmer: "शेतकरी",
    agronomist: "कृषी शास्त्रज्ञ",
    language: "भाषा",
    disclaimer:
      "भूमी बुद्धिमत्ता स्कोर हा अंतर्गत एकत्रित निर्देशांक आहे, अधिकृत कृषी मानक नाही.",
  },
  ta: {
    appName: "பூமி",
    appTagline: "விவசாய நுண்ணறிவு தளம்",
    signIn: "உள்நுழையுங்கள்",
    signUp: "உங்கள் கணக்கை உருவாக்குங்கள்",
    email: "மின்னஞ்சல்",
    password: "கடவுச்சொல்",
    fullName: "முழு பெயர்",
    role: "பங்கு",
    state: "மாநிலம் (விரும்பினால்)",
    signingIn: "உள்நுழைகிறது…",
    creatingAccount: "கணக்கு உருவாக்கப்படுகிறது…",
    createAccount: "கணக்கை உருவாக்கு",
    newToBhoomi: "பூமியில் புதியவரா?",
    alreadyHaveAccount: "ஏற்கனவே கணக்கு உள்ளதா?",
    loading: "பூமி ஏற்றுகிறது…",
    overview: "கண்ணோட்டம்",
    myFarms: "எனது பண்ணைகள்",
    intelligence: "நுண்ணறிவு",
    cropDoctor: "பயிர் மருத்துவர்",
    cooperation: "ஒத்துழைப்பு",
    advisories: "ஆலோசனைகள்",
    settings: "அமைப்புகள்",
    admin: "நிர்வாகி",
    notifications: "அறிவிப்புகள்",
    noNotifications: "இன்னும் அறிவிப்புகள் இல்லை.",
    logOut: "வெளியேறு",
    farmer: "விவசாயி",
    agronomist: "வேளாண் விஞ்ஞானி",
    language: "மொழி",
    disclaimer:
      "பூமி நுண்ணறிவு மதிப்பெண் ஒரு உள்ளார்ந்த கூட்டு குறியீடு, அதிகாரப்பூர்வ வேளாண் தரநிலை அல்ல.",
  },
  gu: {
    appName: "ભૂમિ",
    appTagline: "કૃષિ બુદ્ધિમત્તા પ્લેટફોર્મ",
    signIn: "સાઇન ઇન કરો",
    signUp: "તમારું ખાતું બનાવો",
    email: "ઇમેઇલ",
    password: "પાસવર્ડ",
    fullName: "પૂરું નામ",
    role: "ભૂમિકા",
    state: "રાજ્ય (વૈકલ્પિક)",
    signingIn: "સાઇન ઇન થઈ રહ્યું છે…",
    creatingAccount: "ખાતું બનાવવામાં આવી રહ્યું છે…",
    createAccount: "ખાતું બનાવો",
    newToBhoomi: "ભૂમિમાં નવા છો?",
    alreadyHaveAccount: "પહેલેથી ખાતું છે?",
    loading: "ભૂમિ લોડ થઈ રહ્યું છે…",
    overview: "ઝાંખી",
    myFarms: "મારા ખેતરો",
    intelligence: "બુદ્ધિમત્તા",
    cropDoctor: "પાક ડૉક્ટર",
    cooperation: "સહકાર",
    advisories: "સલાહ",
    settings: "સેટિંગ્સ",
    admin: "એડમિન",
    notifications: "સૂચનાઓ",
    noNotifications: "હજુ સુધી કોઈ સૂચનાઓ નથી.",
    logOut: "લોગ આઉટ",
    farmer: "ખેડૂત",
    agronomist: "કૃષિ વૈજ્ઞાનિક",
    language: "ભાષા",
    disclaimer:
      "ભૂમિ બુદ્ધિમત્તા સ્કોર એક આંતરિક સંયુક્ત સૂચકાંક છે, સત્તાવાર કૃષિ ધોરણ નથી.",
  },
  kn: {
    appName: "ಭೂಮಿ",
    appTagline: "ಕೃಷಿ ಬುದ್ಧಿಮತ್ತೆ ವೇದಿಕೆ",
    signIn: "ಸೈನ್ ಇನ್ ಮಾಡಿ",
    signUp: "ನಿಮ್ಮ ಖಾತೆಯನ್ನು ರಚಿಸಿ",
    email: "ಇಮೇಲ್",
    password: "ಪಾಸ್‌ವರ್ಡ್",
    fullName: "ಪೂರ್ಣ ಹೆಸರು",
    role: "ಪಾತ್ರ",
    state: "ರಾಜ್ಯ (ಐಚ್ಛಿಕ)",
    signingIn: "ಸೈನ್ ಇನ್ ಆಗುತ್ತಿದೆ…",
    creatingAccount: "ಖಾತೆ ರಚಿಸಲಾಗುತ್ತಿದೆ…",
    createAccount: "ಖಾತೆ ರಚಿಸಿ",
    newToBhoomi: "ಭೂಮಿಗೆ ಹೊಸಬರೇ?",
    alreadyHaveAccount: "ಈಗಾಗಲೇ ಖಾತೆ ಇದೆಯೇ?",
    loading: "ಭೂಮಿ ಲೋಡ್ ಆಗುತ್ತಿದೆ…",
    overview: "ಅವಲೋಕನ",
    myFarms: "ನನ್ನ ಹೊಲಗಳು",
    intelligence: "ಬುದ್ಧಿಮತ್ತೆ",
    cropDoctor: "ಬೆಳೆ ವೈದ್ಯ",
    cooperation: "ಸಹಕಾರ",
    advisories: "ಸಲಹೆಗಳು",
    settings: "ಸೆಟ್ಟಿಂಗ್‌ಗಳು",
    admin: "ಅಡ್ಮಿನ್",
    notifications: "ಅಧಿಸೂಚನೆಗಳು",
    noNotifications: "ಇನ್ನೂ ಯಾವುದೇ ಅಧಿಸೂಚನೆಗಳಿಲ್ಲ.",
    logOut: "ಲಾಗ್ ಔಟ್",
    farmer: "ರೈತ",
    agronomist: "ಕೃಷಿ ವಿಜ್ಞಾನಿ",
    language: "ಭಾಷೆ",
    disclaimer:
      "ಭೂಮಿ ಬುದ್ಧಿಮತ್ತೆ ಸ್ಕೋರ್ ಒಂದು ಆಂತರಿಕ ಸಂಯೋಜಿತ ಸೂಚ್ಯಂಕ, ಅಧಿಕೃತ ಕೃಷಿ ಮಾನದಂಡವಲ್ಲ.",
  },
  ml: {
    appName: "ഭൂമി",
    appTagline: "കാർഷിക ബുദ്ധിമത്ത പ്ലാറ്റ്‌ഫോം",
    signIn: "സൈൻ ഇൻ ചെയ്യുക",
    signUp: "നിങ്ങളുടെ അക്കൗണ്ട് സൃഷ്ടിക്കുക",
    email: "ഇമെയിൽ",
    password: "പാസ്‌വേഡ്",
    fullName: "മുഴുവൻ പേര്",
    role: "പങ്ക്",
    state: "സംസ്ഥാനം (ഐച്ഛികം)",
    signingIn: "സൈൻ ഇൻ ചെയ്യുന്നു…",
    creatingAccount: "അക്കൗണ്ട് സൃഷ്ടിക്കുന്നു…",
    createAccount: "അക്കൗണ്ട് സൃഷ്ടിക്കുക",
    newToBhoomi: "ഭൂമിയിൽ പുതിയതാണോ?",
    alreadyHaveAccount: "ഇതിനകം അക്കൗണ്ട് ഉണ്ടോ?",
    loading: "ഭൂമി ലോഡ് ചെയ്യുന്നു…",
    overview: "അവലോകനം",
    myFarms: "എന്റെ കൃഷിയിടങ്ങൾ",
    intelligence: "ബുദ്ധിമത്ത",
    cropDoctor: "വിള ഡോക്ടർ",
    cooperation: "സഹകരണം",
    advisories: "ഉപദേശങ്ങൾ",
    settings: "സെറ്റിംഗ്‌സ്",
    admin: "അഡ്‌മിൻ",
    notifications: "അറിയിപ്പുകൾ",
    noNotifications: "ഇതുവരെ അറിയിപ്പുകളൊന്നുമില്ല.",
    logOut: "ലോഗ് ഔട്ട്",
    farmer: "കർഷകൻ",
    agronomist: "കാർഷിക ശാസ്ത്രജ്ഞൻ",
    language: "ഭാഷ",
    disclaimer:
      "ഭൂമി ബുദ്ധിമത്ത സ്‌കോർ ഒരു ആന്തരിക സംയോജിത സൂചികയാണ്, ഔദ്യോഗിക കാർഷിക മാനദണ്ഡമല്ല.",
  },
  or: {
    appName: "ଭୂମି",
    appTagline: "କୃଷି ବୁଦ୍ଧିମତ୍ତା ପ୍ଲାଟଫର୍ମ",
    signIn: "ସାଇନ ଇନ କରନ୍ତୁ",
    signUp: "ଆପଣଙ୍କ ଆକାଉଣ୍ଟ ସୃଷ୍ଟି କରନ୍ତୁ",
    email: "ଇମେଲ",
    password: "ପାସୱାର୍ଡ",
    fullName: "ସମ୍ପୂର୍ଣ୍ଣ ନାମ",
    role: "ଭୂମିକା",
    state: "ରାଜ୍ୟ (ଇଚ୍ଛାଧୀନ)",
    signingIn: "ସାଇନ ଇନ ହେଉଛି…",
    creatingAccount: "ଆକାଉଣ୍ଟ ସୃଷ୍ଟି ହେଉଛି…",
    createAccount: "ଆକାଉଣ୍ଟ ସୃଷ୍ଟି କରନ୍ତୁ",
    newToBhoomi: "ଭୂମିରେ ନୂଆ?",
    alreadyHaveAccount: "ପୂର୍ବରୁ ଆକାଉଣ୍ଟ ଅଛି?",
    loading: "ଭୂମି ଲୋଡ ହେଉଛି…",
    overview: "ସମୀକ୍ଷା",
    myFarms: "ମୋ ଚାଷ",
    intelligence: "ବୁଦ୍ଧିମତ୍ତା",
    cropDoctor: "ଫସଲ ଡାକ୍ତର",
    cooperation: "ସହଯୋଗ",
    advisories: "ପରାମର୍ଶ",
    settings: "ସେଟିଂସ",
    admin: "ଆଡମିନ",
    notifications: "ସୂଚନା",
    noNotifications: "ଏପର୍ଯ୍ୟନ୍ତ କୌଣସି ସୂଚନା ନାହିଁ।",
    logOut: "ଲଗ ଆଉଟ",
    farmer: "ଚାଷୀ",
    agronomist: "କୃଷି ବିଜ୍ଞାନୀ",
    language: "ଭାଷା",
    disclaimer:
      "ଭୂମି ବୁଦ୍ଧିମତ୍ତା ସ୍କୋର ଏକ ଆଭ୍ୟନ୍ତରୀଣ ସମ୍ମିଳିତ ସୂଚକାଙ୍କ, ସରକାରୀ କୃଷି ମାନଦଣ୍ଡ ନୁହେଁ।",
  },
  pa: {
    appName: "ਭੂਮੀ",
    appTagline: "ਖੇਤੀ ਬੁੱਧੀਮਾਨ ਪਲੇਟਫਾਰਮ",
    signIn: "ਸਾਈਨ ਇਨ ਕਰੋ",
    signUp: "ਆਪਣਾ ਖਾਤਾ ਬਣਾਓ",
    email: "ਈਮੇਲ",
    password: "ਪਾਸਵਰਡ",
    fullName: "ਪੂਰਾ ਨਾਮ",
    role: "ਭੂਮਿਕਾ",
    state: "ਰਾਜ (ਵਿਕਲਪਿਕ)",
    signingIn: "ਸਾਈਨ ਇਨ ਹੋ ਰਿਹਾ ਹੈ…",
    creatingAccount: "ਖਾਤਾ ਬਣਾਇਆ ਜਾ ਰਿਹਾ ਹੈ…",
    createAccount: "ਖਾਤਾ ਬਣਾਓ",
    newToBhoomi: "ਭੂਮੀ 'ਤੇ ਨਵੇਂ ਹੋ?",
    alreadyHaveAccount: "ਪਹਿਲਾਂ ਤੋਂ ਖਾਤਾ ਹੈ?",
    loading: "ਭੂਮੀ ਲੋਡ ਹੋ ਰਿਹਾ ਹੈ…",
    overview: "ਸੰਖੇਪ",
    myFarms: "ਮੇਰੇ ਖੇਤ",
    intelligence: "ਬੁੱਧੀਮਾਨਤਾ",
    cropDoctor: "ਫ਼ਸਲ ਡਾਕਟਰ",
    cooperation: "ਸਹਿਯੋਗ",
    advisories: "ਸਲਾਹ",
    settings: "ਸੈਟਿੰਗਜ਼",
    admin: "ਐਡਮਿਨ",
    notifications: "ਸੂਚਨਾਵਾਂ",
    noNotifications: "ਅਜੇ ਕੋਈ ਸੂਚਨਾ ਨਹੀਂ।",
    logOut: "ਲੌਗ ਆਊਟ",
    farmer: "ਕਿਸਾਨ",
    agronomist: "ਖੇਤੀ ਵਿਗਿਆਨੀ",
    language: "ਭਾਸ਼ਾ",
    disclaimer:
      "ਭੂਮੀ ਬੁੱਧੀਮਾਨਤਾ ਸਕੋਰ ਇੱਕ ਅੰਦਰੂਨੀ ਸੰਯੁਕਤ ਸੂਚਕ ਹੈ, ਸਰਕਾਰੀ ਖੇਤੀ ਮਿਆਰ ਨਹੀਂ।",
  },
  ur: {
    appName: "بھومی",
    appTagline: "زراعتی ذہانت پلیٹ فارم",
    signIn: "سائن ان کریں",
    signUp: "اپنا اکاؤنٹ بنائیں",
    email: "ای میل",
    password: "پاس ورڈ",
    fullName: "پورا نام",
    role: "کردار",
    state: "ریاست (اختیاری)",
    signingIn: "سائن ان ہو رہا ہے…",
    creatingAccount: "اکاؤنٹ بنایا جا رہا ہے…",
    createAccount: "اکاؤنٹ بنائیں",
    newToBhoomi: "بھومی پر نئے ہیں؟",
    alreadyHaveAccount: "پہلے سے اکاؤنٹ ہے؟",
    loading: "بھومی لوڈ ہو رہا ہے…",
    overview: "جائزہ",
    myFarms: "میرے کھیت",
    intelligence: "ذہانت",
    cropDoctor: "فصل ڈاکٹر",
    cooperation: "تعاون",
    advisories: "مشاورت",
    settings: "ترتیبات",
    admin: "ایڈمن",
    notifications: "اطلاعات",
    noNotifications: "ابھی تک کوئی اطلاع نہیں۔",
    logOut: "لاگ آؤٹ",
    farmer: "کسان",
    agronomist: "زراعتی سائنسدان",
    language: "زبان",
    disclaimer:
      "بھومی ذہانت سکور ایک اندرونی مرکب اشاریہ ہے، سرکاری زراعتی معیار نہیں۔",
  },
};

/* ──────────────────────────────────────────────────────────────────────
 * Fallback: for languages without full translations, return English
 * ────────────────────────────────────────────────────────────────────── */
const ENGLISH: Translations = translations.en!;

function getTranslations(lang: string): Partial<Translations> {
  return translations[lang] ?? ENGLISH;
}

/* ──────────────────────────────────────────────────────────────────────
 * Context
 * ────────────────────────────────────────────────────────────────────── */
interface I18nContextType {
  lang: LangCode;
  setLang: (lang: LangCode) => void;
  t: (key: TranslationKeys) => string;
  dir: "ltr" | "rtl";
}

const I18nContext = createContext<I18nContextType>({
  lang: "en",
  setLang: () => {},
  t: (key) => key,
  dir: "ltr",
});

const RTL_LANGS: LangCode[] = ["ur", "sd", "ks"];

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LangCode>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("bhoomi-lang") as LangCode) || "en";
    }
    return "en";
  });

  const setLang = useCallback((newLang: LangCode) => {
    setLangState(newLang);
    if (typeof window !== "undefined") {
      localStorage.setItem("bhoomi-lang", newLang);
    }
  }, []);

  const t = useCallback(
    (key: TranslationKeys): string => {
      const tr = getTranslations(lang);
      return tr[key] ?? ENGLISH[key] ?? key;
    },
    [lang]
  );

  const dir = RTL_LANGS.includes(lang) ? "rtl" : "ltr";

  return (
    <I18nContext.Provider value={{ lang, setLang, t, dir }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
