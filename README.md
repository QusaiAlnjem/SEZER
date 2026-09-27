# SEZER — تطبيق إدارة أعمال الأقمشة

**واجهة**: Next.js 14 (PWA, App Router) + Tailwind — بالكامل بالعربية، اتجاه RTL
**خلفية**: FastAPI + SQLAlchemy + Alembic
**قاعدة البيانات**: PostgreSQL (Supabase)
**التخزين**: Supabase Storage (لملفات PDF/Excel لاستلامات المستودع)
**العملات**: مزدوجة — USD + SYP (كل معاملة تحتفظ بسعر الصرف الخاص بها للحسابات التاريخية)
**تسجيل الدخول**: PIN لمستخدم واحد (المالك)

## المميزات

- **الرئيسية**: تدفق نقدي فوري، مصروفات يومية، صافي الربح، مستحقات الزبائن، تنبيهات المخزون
- **الزبائن**: أرصدة تفصيلية (من دفع، من لم يدفع)، فواتير بيع مع سحب من المخزون، دفعات جزئية
- **المستودع**: بحث بالاسم أو الكود أو الباركود، إنشاء تلقائي للأصناف، رفع PDF/Excel مع استخراج تلقائي

## التشغيل محليًا

### 1) قاعدة البيانات (Supabase — مجانًا)

1. أنشئ حسابًا على https://supabase.com وابدأ مشروعًا جديدًا (اختر إقليمًا قريبًا؛ مثلاً `eu-central-1`).
2. من **Project Settings → Database → Connection string → URI** انسخ الرابط بصيغة `Transaction` (المنفذ 6543).
3. من **Project Settings → API** انسخ `URL` و `service_role` key.
4. من **Storage** أنشئ bucket خاص باسم `inventory-docs`.

### 2) الخلفية (FastAPI)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# عدّل .env بمعلومات Supabase الحقيقية

alembic upgrade head
python seed.py          # اختياري: بيانات تجريبية
uvicorn app.main:app --reload
```

سيعمل الخادم على `http://localhost:8000`. تحقق من `http://localhost:8000/docs` لعرض الـ Swagger.

### 3) الواجهة (Next.js PWA)

```bash
cd frontend
cp .env.example .env.local
# NEXT_PUBLIC_API_BASE=http://localhost:8000  (للتطوير)
npm install
npm run dev
```

افتح http://localhost:3000 وسجّل دخولك بالرمز `1234` (المذكور في `OWNER_PIN`).

> يمكنك تغيير الـ PIN لاحقًا عبر endpoint `POST /api/auth/change-pin`. القيمة الافتراضية تُهش عند أول تشغيل فقط.

## النشر إلى الإنتاج (Vercel + Railway + Supabase)

### الخطوة 1 — Railway (FastAPI)

1. ادفع الكود إلى GitHub (repo واحد يحوي كلا المجلدين مقبول).
2. من https://railway.app → **New Project → Deploy from GitHub** واختر المجلد الفرعي `backend`.
3. Railway سيلتقط `Dockerfile` تلقائيًا.
4. أضف متغيرات البيئة (من ملف `.env.example`):
   - `DATABASE_URL` (Supabase pooled URI, المنفذ 6543)
   - `JWT_SECRET` (سلسلة عشوائية طويلة)
   - `OWNER_PIN` (الرمز السري الافتراضي عند أول تشغيل فقط)
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_BUCKET=inventory-docs`
   - `CORS_ORIGINS=https://your-app.vercel.app` (سيُملأ لاحقًا)
5. Deploy. سيمنحك رابطًا مثل `https://sezer-api.up.railway.app`. الـ Dockerfile يشغّل `alembic upgrade head` تلقائيًا عند الإقلاع، فالجداول تُنشأ تلقائيًا.
6. جرب `curl https://sezer-api.up.railway.app/api/health` — يجب أن يعيد `{"ok": true}`.

### الخطوة 2 — Vercel (Next.js)

1. https://vercel.com → **Import Project** من نفس الـ repo، الجذر: `frontend/`.
2. أضف متغير البيئة `NEXT_PUBLIC_API_BASE=https://sezer-api.up.railway.app`.
3. Deploy. Vercel سيعطيك رابطًا مثل `https://sezer.vercel.app`.
4. عد لـ Railway وضع `CORS_ORIGINS=https://sezer.vercel.app` ثم أعِد النشر.
5. من الهاتف: افتح رابط Vercel في Chrome/Safari → **إضافة إلى الشاشة الرئيسية** — سيُثبَّت التطبيق كأنه أصلي (PWA).

### الخطوة 3 — قواعد Supabase Storage

في محرر SQL لـ Supabase، شغّل هذه القاعدة لحماية bucket المستندات (لأننا نستخدم service role من الخادم فقط):

```sql
-- منع الوصول المباشر من المتصفح — كل الوصول عبر service_role
alter policy "Give users authenticated access to folder"
on "storage"."objects"
using (auth.role() = 'service_role');
```

## الحدود المجانية

| الخدمة   | الحد المجاني                                    | كافٍ لـ SEZER؟ |
|----------|-------------------------------------------------|-----------------|
| Supabase | 500 MB PostgreSQL, 1 GB storage, unlimited API requests | نعم بسهولة — الجدول الرئيسي مضغوط |
| Railway  | $5 credit/شهر (يكفي لخدمة FastAPI صغيرة)         | نعم — الاستهلاك ~$3/شهر |
| Vercel   | 100 GB bandwidth شهريًا للـ Hobby                | نعم — التطبيق خفيف |

## أوامر مفيدة

```bash
# إعادة بناء قاعدة البيانات من الصفر (تحذير: تحذف كل شيء)
cd backend
alembic downgrade base && alembic upgrade head

# تحديث سعر الصرف يوميًا
curl -X POST https://sezer-api.up.railway.app/api/fx \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"day":"2026-08-31","syp_per_usd":15200,"source":"manual"}'
```

## هيكل المستودع

```
sezer/
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── main.py           # نقطة الدخول
│   │   ├── core/config.py    # إعدادات البيئة
│   │   ├── database.py       # SQLAlchemy engine
│   │   ├── models/           # جداول قاعدة البيانات
│   │   ├── schemas/          # Pydantic DTOs
│   │   ├── services/         # منطق الأعمال (fx, auth, storage, inventory...)
│   │   └── routers/          # نقاط REST (بادئة /api)
│   ├── alembic/              # هجرات قاعدة البيانات
│   ├── seed.py               # بيانات تجريبية
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # Next.js 14
│   ├── src/
│   │   ├── app/              # الصفحات (App Router)
│   │   │   ├── page.tsx      # الرئيسية
│   │   │   ├── login/
│   │   │   ├── creditors/
│   │   │   └── storage/
│   │   ├── components/       # AppShell, Modal, StatCard, CashflowChart, ...
│   │   ├── lib/              # api.ts, format.ts
│   │   └── types/
│   ├── public/               # manifest.json, icons
│   ├── next.config.js        # next-pwa
│   └── package.json
└── docs/schema.md            # وثيقة الـ ERD
```

## قرار قاعدة البيانات: لماذا PostgreSQL بدلاً من Firebase؟

- **العلائقية**: أصناف ← استلامات ← مستودع ← فواتير ← دفعات — كل شيء ينضم بمفاتيح خارجية. Firebase (NoSQL) يتطلب إزالة تطبيع مؤلمة.
- **التقارير**: الرئيسية تعتمد `SUM/GROUP BY` معقّدة عبر تواريخ متعددة (revenue, COGS, opex). SQL يفعلها في استعلام واحد؛ Firebase يفعلها في المتصفح بكلفة قراءات ضخمة.
- **العملات المزدوجة**: نخزّن سعر صرف مع كل معاملة لتجنّب الانحراف الحسابي — أسهل بكثير في مخطط علائقي.
- **التسعير**: Supabase مجاني حتى 500 MB (يكفي عشرات آلاف الفواتير)، Firebase مجاني ولكن قراءاته اللانهائية تكسر عند تشغيل تقرير مالي كبير.
- **الملاءمة مع FastAPI**: Firebase عمليًا يعني تخطي FastAPI واستخدام Firebase SDK من المتصفح مباشرة.

## أفكار للمرحلة التالية

- شاشة إعدادات (تغيير PIN، تحديث سعر الصرف يدويًا، رفع الشعار)
- قائمة العمليات الأخيرة على الرئيسية (آخر 5 فواتير + آخر 5 دفعات)
- طباعة الفواتير بصيغة PDF عربية
- استيراد OCR من صور الفواتير (Tesseract أو Google Vision)
- Backup تلقائي أسبوعي إلى Google Drive
- عرض تفاصيل زبون واحد على صفحة مستقلة إذا احتيج

---
SEZER · مبني بحبّ للأقمشة السورية 🧵
