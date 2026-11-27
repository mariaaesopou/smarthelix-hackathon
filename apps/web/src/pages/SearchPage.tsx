import {useEffect, useState, type FormEvent} from "react";
import {Link, useSearchParams} from "react-router";
import {api, TYPE_LABELS, type ProfilePage} from "../api";

export default function SearchPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const q = searchParams.get("q") ?? "";

    const [result, setResult] = useState<ProfilePage | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    // Runs on first render and again whenever q changes.
    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        api
            .searchProfiles({ q })
            .then((page) => {
                if (!cancelled) setResult(page);
            })
            .catch((err: unknown) => {
                if (!cancelled) setError(err instanceof Error ? err.message : "Something went wrong");
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        // Cleanup: if q changes before this request finishes, ignore its answer.
        return () => {
            cancelled = true;
        };
    }, [q]);

    function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const value = new FormData(event.currentTarget).get("q")?.toString().trim() ?? "";
        setSearchParams(value ? { q: value } : {});
    }

    return (
        <section>
            <h1>Search</h1>
            <form key={q} role="search" onSubmit={handleSubmit}>
                <input name="q" defaultValue={q} placeholder="Search..." />
                <button type="submit">Search</button>
            </form>

            {loading && <p>Loading…</p>}
            {error && <p role="alert">{error}</p>}
            {result && !loading && !error && (
                <>
                    <p>{result.total} profiles found</p>
                    <ul>
                        {result.items.map((p) => (
                            <li key={p.id}>
                                <Link to={`/profiles/${p.id}`}>{p.name}</Link> · {TYPE_LABELS[p.type]} ·{" "}
                                {p.region ?? "No region"}
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </section>
    );
}
