import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { AlertCircleIcon, CheckCircle2, ChevronLeftIcon } from "lucide-react";
import { useTheme } from "@/lib/theme-context";

const gradientOuter =
  "relative w-full rounded-xl p-[1px] bg-[radial-gradient(circle_at_top,rgba(250,236,210,0.7),rgba(124,95,72,1))]";
const gradientInner =
  "rounded-xl bg-[linear-gradient(196deg,rgba(211,193,173,1)_0%,rgba(192,168,143,1)_15%,rgba(155,123,95,1)_82%,rgba(124,95,72,1)_100%)]";

export const GnrateurOrdonnances = () => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [edmBasePath] = useState<string>("C:/Stimut/Documents_Patients");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      setError(null);
      setResult(null);
    }
  };

  const handleProcess = async () => {
    if (!uploadedFile) return;
    setProcessing(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", uploadedFile);
      formData.append("edm_base_path", edmBasePath);

      // Determine which endpoint to use
      const isZip = uploadedFile.name.toLowerCase().endsWith(".zip");
      const endpoint = isZip ? "process-zip" : "parse-and-generate";
      const url = `http://localhost:7861/${endpoint}`;
      console.log("Uploading file:", uploadedFile.name);
      console.log("Is ZIP?", isZip);
      console.log("URL:", url);

      const response = await fetch(url, {
        method: "POST",
        body: formData,
      });
      console.log("Response status:", response.status);
      const data = await response.json();
      if (data.success) {
        setResult(data);
      } else {
        setError(data.message || data.error || "Échec de la génération");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur réseau");
    } finally {
      setProcessing(false);
    }
  };

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
              {uploadedFile && (
                <Button
                  onClick={handleProcess}
                  disabled={processing}
                  className="px-8 py-2 rounded-full bg-white/20 text-white hover:bg-white/30 disabled:opacity-50"
                >
                  {processing ? "Traitement en cours..." : "Analyser et générer l'ordonnance"}
                </Button>
              )}
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
    </div>
  );
};