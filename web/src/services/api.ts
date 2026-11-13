import axios from "axios";
import type { RawAxiosHeaders } from "axios";
import type { MessageDescriptor } from "@/i18n";
import en from "@/i18n/en";

export type ApiClientErrorKind =
  "contract_mismatch" | "http_error" | "network_error" | "timeout" | "canceled";

export type ApiClientErrorOptions = {
  code?: string;
  requestId?: string;
  retryAfter?: string;
  status?: number;
};

type ApiErrorBody = {
  code: string;
  error: string;
  requestId: string;
};

export class ApiClientError extends Error {
  readonly code: string | undefined;
  readonly kind: ApiClientErrorKind;
  readonly requestId: string | undefined;
  readonly retryAfter: string | undefined;
  readonly status: number | undefined;

  constructor(message: string, kind: ApiClientErrorKind, options: ApiClientErrorOptions = {}) {
    super(message);
    this.name = "ApiClientError";
    this.kind = kind;
    this.code = options.code;
    this.requestId = options.requestId;
    this.retryAfter = options.retryAfter;
    this.status = options.status;
  }
}

export function describeApiError(caught: unknown, fallback: string): MessageDescriptor {
  if (caught instanceof ApiClientError) {
    const code = caught.code;
    const key = code && Object.hasOwn(en.errors, code) ? `errors.${code}` : fallback;
    return { key, requestId: caught.requestId };
  }
  return { key: fallback };
}

export const apiClient = axios.create({
  responseType: "json",
  transitional: { silentJSONParsing: false },
});

apiClient.interceptors.response.use(
  (response) => {
    if (
      response.status === 204 ||
      response.status === 205 ||
      response.config.method === "head" ||
      isJsonContentType(headerValue(response.headers, "content-type"))
    ) {
      return response;
    }

    return Promise.reject(
      new ApiClientError("Unexpected API success response.", "contract_mismatch", {
        requestId:
          headerValue(response.headers, "X-Request-Id") ??
          headerValue(response.config.headers, "X-Request-Id"),
        status: response.status,
      }),
    );
  },
  (caught: unknown) => Promise.reject(normalizeApiError(caught)),
);

function normalizeApiError(caught: unknown): ApiClientError {
  if (caught instanceof ApiClientError) {
    return caught;
  }

  if (!axios.isAxiosError(caught) || !caught.response) {
    const options = {
      requestId: axios.isAxiosError(caught)
        ? headerValue(caught.config?.headers, "X-Request-Id")
        : undefined,
    };

    if (axios.isCancel(caught)) {
      return new ApiClientError("Request canceled.", "canceled", options);
    }
    if (
      axios.isAxiosError(caught) &&
      (caught.code === axios.AxiosError.ECONNABORTED || caught.code === axios.AxiosError.ETIMEDOUT)
    ) {
      return new ApiClientError("Request timed out.", "timeout", options);
    }
    return new ApiClientError("Network request failed.", "network_error", options);
  }

  const { data, headers, status } = caught.response;
  const requestId =
    headerValue(headers, "X-Request-Id") ??
    (isApiErrorBody(data) ? data.requestId : undefined) ??
    headerValue(caught.config?.headers, "X-Request-Id");

  const options = { requestId, retryAfter: headerValue(headers, "Retry-After"), status };

  if (!isJsonContentType(headerValue(headers, "content-type")) || !isApiErrorBody(data)) {
    return new ApiClientError(
      status < 400 ? "Unexpected API success response." : "Unexpected API error response.",
      "contract_mismatch",
      options,
    );
  }

  return new ApiClientError(data.error, "http_error", {
    code: data.code,
    ...options,
  });
}

function isJsonContentType(contentType: string | undefined): boolean {
  const mediaType = contentType?.split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json" || mediaType?.endsWith("+json") === true;
}

function headerValue(headers: unknown, name: string): string | undefined {
  const value = axios.AxiosHeaders.from(headers as RawAxiosHeaders | undefined).get(name);
  return typeof value === "string" ? value : undefined;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }

  const body = value as Record<string, unknown>;
  return (
    typeof body.code === "string" &&
    body.code.trim() !== "" &&
    typeof body.error === "string" &&
    body.error.trim() !== "" &&
    typeof body.requestId === "string" &&
    body.requestId.trim() !== ""
  );
}
