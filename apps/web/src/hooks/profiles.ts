import {useEffect, useState, type FormEvent, type RefObject} from "react";
import {useSearchParams} from "react-router";
import {api, NotFoundError, TYPE_LABELS, type Profile, type ProfilePage, type ProfileType} from "../api";

// Data logic for the search and profile pages, so the pages only contain markup.

export const TYPES = Object.keys(TYPE_LABELS) as ProfileType[];

function isProfileType(value: string | null): value is ProfileType {
    return value !== null && (TYPES as string[]).includes(value);
}

// Search state lives in the URL (?q=...&type=...), so it survives opening a profile.
export function useProfileSearch() {
    const [searchParams, setSearchParams] = useSearchParams();
    const q = searchParams.get("q") ?? "";
    const rawType = searchParams.get("type");
    const type = isProfileType(rawType) ? rawType : undefined;

    const [result, setResult] = useState<ProfilePage | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    // Runs on first render and again whenever q or type changes.
    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        api
            .searchProfiles({q, type})
            .then((page) => {
                if (!cancelled) setResult(page);
            })
            .catch((err: unknown) => {
                if (!cancelled) setError(err instanceof Error ? err.message : "Something went wrong");
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        // Cleanup: if q or type changes before this request finishes, ignore its answer.
        return () => {
            cancelled = true;
        };
    }, [q, type]);

    function updateParams(next: {q?: string; type?: ProfileType}) {
        const params: Record<string, string> = {};
        if (next.q) params.q = next.q;
        if (next.type) params.type = next.type;
        setSearchParams(params);
    }

    function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const value = new FormData(event.currentTarget).get("q")?.toString().trim() ?? "";
        updateParams({q: value, type});
    }

    return {q, type, result, error, loading, updateParams, handleSubmit};
}

export function useProfile(id: string) {
    const [profile, setProfile] = useState<Profile | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setProfile(null);
        setError(null);
        api
            .getProfile(id)
            .then((p) => {
                if (!cancelled) setProfile(p);
            })
            .catch((err: unknown) => {
                if (cancelled) return;
                setError(
                    err instanceof NotFoundError
                        ? "We couldn't find this profile."
                        : "Something went wrong loading this profile.",
                );
            });
        return () => {
            cancelled = true;
        };
    }, [id]);

    return {profile, error};
}

// On narrow screens the detail panel sits above the list, so bring it into view when a profile opens.
export function useScrollIntoViewOnMobile(ref: RefObject<HTMLElement | null>, key: string) {
    useEffect(() => {
        if (ref.current && window.matchMedia("(max-width: 900px)").matches) {
            ref.current.scrollIntoView({behavior: "smooth", block: "start"});
        }
    }, [ref, key]);
}

export function initials(name: string): string {
    return name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0]!.toUpperCase())
        .join("");
}

export function formatDate(iso: string): string {
    const date = new Date(iso);
    return Number.isNaN(date.getTime())
        ? iso
        : date.toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric"});
}
