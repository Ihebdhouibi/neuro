import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { AlertCircleIcon, CheckCircle2, ChevronLeftIcon } from "lucide-react";
import { useTheme } from "@/lib/theme-context";
import {
  PrescriptionPDFViewer as PrescriptionPDFViewerDefault,
  PrescriptionData,
} from "./templates/PrescriptionPDF";

const gradientOuter =
  "relative w-full rounded-xl p-[1px] bg-[radial-gradient(circle_at_top,rgba(250,236,210,0.7),rgba(124,95,72,1))]";
const gradientInner =
  "rounded-xl bg-[linear-gradient(196deg,rgba(211,193,173,1)_0%,rgba(192,168,143,1)_15%,rgba(155,123,95,1)_82%,rgba(124,95,72,1)_100%)]";

const PRESCRIBERS = [
  { initials: "DM", name: "Dr. Martin", rpps: "RPPS-123456" },
  { initials: "DL", name: "Dr. Leroy", rpps: "RPPS-987654" },
];

// Helper to get backend URL (overridable via window.__BACKEND_URL injected by main process)
const BACKEND_URL =
  (typeof window !== "undefined" && (window as any).__BACKEND_URL) ||
  "http://localhost:7861";

export const GnrateurOrdonnances = () => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [edmBasePath] = useState<string>("C:/Stimut/Documents_Patients");
  const [maxFrames, setMaxFrames] = useState<number>(0);
  const [progress, setProgress] = useState<number | null>(null);
  const [, setPolling] = useState(false);
  const [isB2ModalOpen, setIsB2ModalOpen] = useState(false);
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      console.log(
        `[FRONTEND] File selected: ${file.name}, size: ${file.size} bytes, type: ${file.type}`,
      );
      setUploadedFile(file);
      setError(null);
      setResult(null);
      setProgress(null);
    } else {
      console.log("[FRONTEND] No file selected");
    }
  };

  const startPolling = (jobId: string) => {
    setPolling(true);
    const interval = setInterval(async () => {
      try {
        const statusRes = await fetch(`${BACKEND_URL}/job/${jobId}/status`);
        const status = await statusRes.json();
        console.log(`[FRONTEND] Job ${jobId} progress: ${status.progress}%`);
        setProgress(status.progress);
        if (status.finished) {
          clearInterval(interval);
          setPolling(false);
          if (status.result && status.result.success) {
            setResult(status.result);
          } else {
            setError(
              status.result?.error || status.message || "Erreur lors du traitement",
            );
          }
          setProcessing(false);
        }
      } catch (err) {
        console.error("Polling error:", err);
        clearInterval(interval);
        setPolling(false);
        setError("Erreur lors du suivi de l'avancement");
        setProcessing(false);
      }
    }, 1000);
  };

  const handleProcess = async () => {
    if (!uploadedFile) return;
    setProcessing(true);
    setError(null);
    setResult(null);
    setProgress(null);

    try {
      const formData = new FormData();
      formData.append("file", uploadedFile);
      formData.append("edm_base_path", edmBasePath);

      const isZip = uploadedFile.name.toLowerCase().endsWith(".zip");
      let url = isZip
        ? `${BACKEND_URL}/process-zip-async`
        : `${BACKEND_URL}/process-file-async`;

      if (isZip && maxFrames > 0) {
        url += `?max_frames=${maxFrames}`;
      }

      console.log(`[FRONTEND] Sending async request to ${url}`);
      const response = await fetch(url, { method: "POST", body: formData });
      const { job_id } = await response.json();
      console.log(`[FRONTEND] Job created: ${job_id}`);
      startPolling(job_id);
    } catch (err) {
      console.error("Processing error:", err);
      setError(err instanceof Error ? err.message : "Erreur réseau");
      setProcessing(false);
    }
  };

  const isZipFile = !!uploadedFile && uploadedFile.name.toLowerCase().endsWith(".zip");

  return (
    <div className="min-h-screen w-full p-6" style={{ backgroundColor: colors.background }}>
      {/* Fixed home button */}
      <button
        onClick={() => navigate("/")}
        className="fixed top-24 left-4 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 transition-colors"
        aria-label="Accueil"
      >
        🏠
      </button>

      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header with back button */}
        <div className="flex items-center gap-4">
          <Button
            onClick={() => navigate("/menu")}
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-full bg-white/10 hover:bg-white/20"
          >
            <ChevronLeftIcon className="h-5 w-5 text-[#faecd2]" />
          </Button>
          <h1 className="text-2xl font-bold" style={{ color: colors.text }}>
            Générateur d'ordonnances
          </h1>
        </div>

        {/* Upload card */}
        <div className={gradientOuter}>
          <div className={`${gradientInner} p-6 rounded-xl`}>
            <div className="text-center mb-6">
              <p className="text-white/80">
                Téléchargez une image, un PDF ou un fichier ZIP contenant plusieurs images (frames). 
                Le système extraira automatiquement les données et générera une ordonnance.
              </p>
            </div>

            <div className="flex flex-col items-center gap-4">
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.zip"
                onChange={handleFileChange}
                className="text-white file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-white/20 file:text-white hover:file:bg-white/30"
              />

              {isZipFile && (
                <label className="flex items-center gap-2 text-sm text-white/90">
                  <span>Frames max (0 = toutes) :</span>
                  <input
                    type="number"
                    min={0}
                    value={maxFrames}
                    onChange={(e) => setMaxFrames(parseInt(e.target.value || "0", 10))}
                    className="w-20 rounded bg-white/20 px-2 py-1 text-white placeholder:text-white/60"
                  />
                </label>
              )}

              {uploadedFile && (
                <Button
                  onClick={handleProcess}
                  disabled={processing}
                  className="px-8 py-2 rounded-full bg-white/20 text-white hover:bg-white/30 disabled:opacity-50"
                >
                  {processing ? "Traitement en cours..." : "Analyser et générer l'ordonnance"}
                </Button>
              )}

              {processing && progress !== null && (
                <div className="w-full max-w-md">
                  <div className="h-2 w-full overflow-hidden rounded-full bg-white/20">
                    <div
                      className="h-full bg-white transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
                    />
                  </div>
                  <p className="mt-1 text-center text-xs text-white/80">{progress}%</p>
                </div>
              )}

              <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
                <Button
                  onClick={() => setIsB2ModalOpen(true)}
                  variant="outline"
                  className="rounded-full border-white/40 bg-white/10 text-white hover:bg-white/20"
                >
                  Mode B2 (auto)
                </Button>
                <Button
                  onClick={() => setIsManualModalOpen(true)}
                  variant="outline"
                  className="rounded-full border-white/40 bg-white/10 text-white hover:bg-white/20"
                >
                  Mode Manuel
                </Button>
              </div>
            </div>

            {error && (
              <div className="mt-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg flex items-center gap-2">
                <AlertCircleIcon className="h-5 w-5" />
                <span>{error}</span>
              </div>
            )}

            {result && result.success && (
              <div className="mt-6 p-4 bg-green-100 border border-green-400 text-green-700 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="font-semibold">Prescription générée avec succès !</span>
                </div>
                <p className="text-sm">{result.message}</p>
                <p className="text-sm">PDF enregistré dans : {result.edm_path}</p>
                {result.pdf_path && (
                  <a
                    href={`file:///${result.pdf_path.replace(/\\/g, '/')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm underline mt-2 inline-block"
                  >
                    Ouvrir le PDF
                  </a>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Informative card */}
        <div className={gradientOuter}>
          <div className={`${gradientInner} p-6 rounded-xl text-white/80`}>
            <h3 className="font-semibold mb-2">Fonctionnement</h3>
            <ul className="list-disc list-inside text-sm space-y-1">
              <li>Formats supportés : images (JPG, PNG), PDF, ZIP (contenant plusieurs images ou PDFs).</li>
              <li>Pour un ZIP, le système traite tous les fichiers et combine les données pour générer une seule ordonnance.</li>
              <li>Les données (IPP, FSE, AMY) sont extraites automatiquement.</li>
              <li>Le PDF est enregistré dans le dossier patient selon la structure EDM.</li>
            </ul>
          </div>
        </div>
      </div>

      {isB2ModalOpen && (
        <B2Modal onClose={() => setIsB2ModalOpen(false)} edmBasePath={edmBasePath} />
      )}
      {isManualModalOpen && (
        <ManualModal onClose={() => setIsManualModalOpen(false)} edmBasePath={edmBasePath} />
      )}
    </div>
  );
};

// ---------- B2 Mode Modal ----------
const B2Modal = ({
  onClose,
  edmBasePath,
}: {
  onClose: () => void;
  edmBasePath: string;
}) => {
  const [searchNumber, setSearchNumber] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!searchNumber.trim()) {
      console.warn("[FRONTEND][B2] Search number empty");
      return;
    }
    console.log(`[FRONTEND][B2] Searching for number: ${searchNumber}`);
    setLoading(true);
    setError(null);
    try {
      const lookupRes = await fetch(`${BACKEND_URL}/b2-lookup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number: searchNumber.trim() }),
      });
      const lookupData = await lookupRes.json();
      console.log(`[FRONTEND][B2] Lookup response: success=${lookupData.success}`);
      if (!lookupData.success) throw new Error(lookupData.error || "Numéro non trouvé");

      console.log("[FRONTEND][B2] Generating prescription...");
      const genRes = await fetch(`${BACKEND_URL}/generate-prescription`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient: lookupData.patient,
          prescriber_initials: lookupData.prescriber_initials,
          amy_code: lookupData.amy_code,
          finess: lookupData.finess,
          fse_number: lookupData.fse_number,
          edm_base_path: edmBasePath,
        }),
      });
      const genData = await genRes.json();
      console.log(`[FRONTEND][B2] Generation response: success=${genData.success}`);
      if (!genData.success) throw new Error(genData.error);

      const email = prompt("Veuillez entrer l'adresse email pour recevoir l'ordonnance :");
      if (email) {
        console.log(`[FRONTEND][B2] Sending email to ${email}`);
        const emailRes = await fetch(`${BACKEND_URL}/send-prescription-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pdf_path: genData.pdf_path, email_to: email }),
        });
        const emailData = await emailRes.json();
        if (!emailData.success) throw new Error(emailData.error);
        alert("Ordonnance générée et envoyée par email !");
      } else {
        alert("Ordonnance générée (email non envoyé)");
      }
      console.log("[FRONTEND][B2] Process completed successfully, closing modal");
      onClose();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Erreur";
      console.error(`[FRONTEND][B2] Error: ${errorMsg}`, err);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md rounded-xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute right-3 top-3 text-gray-500 hover:text-gray-700"
          aria-label="Fermer"
        >
          ✕
        </button>
        <h2 className="mb-4 text-xl font-bold text-gray-900">Mode B2 - Automatique</h2>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          Numéro B2 ou FSE
        </label>
        <input
          type="text"
          placeholder="Ex: 553381"
          value={searchNumber}
          onChange={(e) => setSearchNumber(e.target.value)}
          className="mb-2 w-full rounded border px-3 py-2 text-black placeholder:text-gray-400"
        />
        <Button onClick={handleGenerate} disabled={loading} className="w-full">
          {loading ? "Recherche et génération..." : "Générer l'ordonnance"}
        </Button>
        {error && <div className="mt-2 text-red-500">{error}</div>}
      </div>
    </div>
  );
};

// ---------- Manual Mode Modal ----------
const ManualModal = ({
  onClose,
  edmBasePath,
}: {
  onClose: () => void;
  edmBasePath: string;
}) => {
  const [form, setForm] = useState({
    lastName: "",
    firstName: "",
    ssn: "",
    ipp: "",
    fseNumber: "",
    amyCode: "",
    prescriberInitials: "DM",
    email: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPrescriber = PRESCRIBERS.find(
    (p) => p.initials === form.prescriberInitials,
  );

  const prescriptionData: PrescriptionData = {
    form_date: new Date().toISOString().split("T")[0],
    patient: {
      last_name: form.lastName || null,
      first_name: form.firstName || null,
      nir: form.ssn || null,
      birth_date: null,
    },
    doctor: {
      full_name: selectedPrescriber?.name || null,
      rpps: selectedPrescriber?.rpps || null,
    },
    orthoptic_care: {
      description: null,
      acts_prescribed: form.amyCode ? [form.amyCode] : [],
    },
    ocr_raw_text: null,
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    setError(null);
  };

  const handleSubmit = async () => {
    if (
      !form.lastName.trim() ||
      !form.firstName.trim() ||
      !form.ipp.trim() ||
      !form.fseNumber.trim() ||
      !form.amyCode.trim()
    ) {
      setError(
        "Veuillez remplir tous les champs obligatoires (Nom, Prénom, IPP, N° FSE, Code AMY)",
      );
      return;
    }
    setLoading(true);
    try {
      const payload = {
        patient: {
          lastName: form.lastName,
          firstName: form.firstName,
          ssn: form.ssn,
          ipp: form.ipp,
        },
        prescriber_initials: form.prescriberInitials,
        amy_code: form.amyCode,
        finess: "920036563",
        fse_number: form.fseNumber,
        edm_base_path: edmBasePath,
      };
      const genRes = await fetch(`${BACKEND_URL}/generate-prescription`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const genData = await genRes.json();
      if (!genData.success) throw new Error(genData.error);

      if (form.email) {
        const emailRes = await fetch(`${BACKEND_URL}/send-prescription-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pdf_path: genData.pdf_path,
            email_to: form.email,
          }),
        });
        const emailData = await emailRes.json();
        if (!emailData.success) throw new Error(emailData.error);
        alert("Ordonnance générée et envoyée par email !");
      } else {
        alert("Ordonnance générée !");
      }
      onClose();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Erreur";
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "w-full rounded border px-3 py-2 text-black placeholder:text-gray-400";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] w-full max-w-3xl overflow-auto rounded-xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute right-3 top-3 text-gray-500 hover:text-gray-700"
          aria-label="Fermer"
        >
          ✕
        </button>
        <h2 className="mb-4 text-center text-xl font-bold text-gray-900">
          Mode Manuel - Saisie complète
        </h2>

        <div className="mb-6 space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Nom *
              </label>
              <input
                name="lastName"
                value={form.lastName}
                onChange={handleChange}
                className={inputClass}
                placeholder="Dupont"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Prénom *
              </label>
              <input
                name="firstName"
                value={form.firstName}
                onChange={handleChange}
                className={inputClass}
                placeholder="Jean"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                N° de sécurité sociale (NIR)
              </label>
              <input
                name="ssn"
                value={form.ssn}
                onChange={handleChange}
                className={inputClass}
                placeholder="1 85 12 75 123 456 78"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                IPP *
              </label>
              <input
                name="ipp"
                value={form.ipp}
                onChange={handleChange}
                className={inputClass}
                placeholder="P0123456"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                N° FSE *
              </label>
              <input
                name="fseNumber"
                value={form.fseNumber}
                onChange={handleChange}
                className={inputClass}
                placeholder="553381"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Code AMY *
              </label>
              <input
                name="amyCode"
                value={form.amyCode}
                onChange={handleChange}
                className={inputClass}
                placeholder="AMY 13.5"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Prescripteur
              </label>
              <select
                name="prescriberInitials"
                value={form.prescriberInitials}
                onChange={handleChange}
                className={inputClass}
              >
                {PRESCRIBERS.map((p) => (
                  <option key={p.initials} value={p.initials}>
                    {p.name} ({p.initials})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Email (optionnel)
              </label>
              <input
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                className={inputClass}
                placeholder="patient@example.com"
              />
            </div>
          </div>

          {error && <div className="text-sm text-red-600">{error}</div>}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={loading}>
              Annuler
            </Button>
            <Button onClick={handleSubmit} disabled={loading}>
              {loading ? "Génération..." : "Générer l'ordonnance"}
            </Button>
          </div>
        </div>

        <div className="rounded border bg-gray-50 p-4">
          <h3 className="mb-2 text-center font-bold text-gray-900">
            Aperçu de l'ordonnance
          </h3>
          <div className="max-h-[500px] overflow-auto">
            <PrescriptionPDFViewerDefault
              data={prescriptionData}
              width="100%"
              height="auto"
            />
          </div>
        </div>
      </div>
    </div>
  );
};