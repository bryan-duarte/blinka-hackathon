import type {
  BillSourceType,
  DecisionActor,
  EvidenceRole,
  FileScanStatus,
  IdentifierKind,
  PayeeKind,
  PayeeStatus,
  PaymentCategory,
  PaymentMethod,
  Verdict,
} from "./types";

export const CATEGORY_LABELS: Record<PaymentCategory, string> = {
  cloud: "Cloud",
  saas: "Software (SaaS)",
  contractor: "Contratistas",
  professional_services: "Servicios profesionales",
  utilities: "Servicios básicos",
  rent: "Arriendo",
  marketing: "Marketing",
  other: "Otros",
};

export const PAYMENT_CATEGORIES = Object.keys(CATEGORY_LABELS) as PaymentCategory[];

export const PAYEE_KIND_LABELS: Record<PayeeKind, string> = {
  service: "Servicio",
  person: "Persona",
  company: "Empresa",
};

export const PAYEE_KIND_GROUP_LABELS: Record<PayeeKind, string> = {
  service: "Servicios",
  person: "Personas",
  company: "Empresas",
};

export const PAYEE_STATUS_LABELS: Record<PayeeStatus, string> = {
  allowed: "Permitido",
  blacklisted: "Bloqueado",
};

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  bank_transfer: "Transferencia bancaria",
  card_on_file: "Tarjeta registrada",
  platform_debit: "Débito en plataforma",
};

export const IDENTIFIER_KIND_LABELS: Record<IdentifierKind, string> = {
  tax_id: "Identificador tributario",
  bank_account: "Cuenta bancaria",
  service_account_id: "Cuenta de servicio",
  email: "Correo",
  domain: "Dominio",
  alias: "Nombre o alias",
};

export const IDENTIFIER_KINDS = Object.keys(IDENTIFIER_KIND_LABELS) as IdentifierKind[];

export const VERDICT_LABELS: Record<Verdict, string> = {
  pay: "Pagada",
  hold: "Frenada",
  review: "En revisión",
};

export const ACTOR_LABELS: Record<DecisionActor, string> = {
  agent: "Agente",
  human: "Persona",
};

export const FIELD_LABELS: Record<string, string> = {
  payee_name: "Beneficiario",
  amount: "Monto",
  currency: "Moneda",
  payee_country: "País del beneficiario",
  issuer_tax_country: "País tributario del emisor",
  bank_account_country: "País de la cuenta",
  due_date: "Vencimiento",
  issue_date: "Emisión",
  invoice_number: "N° factura",
  bank_account: "Cuenta de destino",
  payee_email: "Correo del beneficiario",
  service_account_id: "Cuenta de servicio",
  provider_domain: "Dominio",
  national_id: "Identificación",
  tax_id: "Identificador tributario",
  legal_name: "Razón social",
  concept: "Concepto",
};

export const SOURCE_LABELS: Record<BillSourceType, string> = {
  email: "Correo",
  upload: "Consola",
  chat: "Chat",
  telegram: "Telegram",
  whatsapp: "WhatsApp",
};

export const EVIDENCE_ROLE_LABELS: Record<EvidenceRole, string> = {
  primary: "Fuente de los datos",
  secondary: "Respaldo",
  archive: "Archivo ZIP recibido",
};

export const SCAN_LABELS: Record<FileScanStatus, string> = {
  clean: "Escaneado por AWS",
  unsupported: "Sin escaneo",
  disabled: "Sin escaneo",
  pending: "Escaneo pendiente",
  threat: "Amenaza detectada",
  failed: "Escaneo fallido",
};

export const RUN_STEP_LABELS: Record<string, string> = {
  started: "Recibido",
  classified: "Clasificado",
  not_a_bill: "No es factura",
  extracted: "Datos extraídos",
  extraction_failed: "Sin datos legibles",
  claimed: "Registrada",
  decided: "Decidido",
  decision_failed: "Falló la decisión",
  completed: "Listo",
  cancelled: "Cancelado",
  failed: "Error",
};

export const EXTRACTION_METHOD_LABELS: Record<string, string> = {
  xml: "factura electrónica XML",
  xml_llm: "XML leído por el modelo",
  textract: "lectura de AWS Textract",
  pdf_text: "texto del PDF leído por el modelo",
  pdf: "PDF leído por el modelo",
  email: "cuerpo del correo",
};
