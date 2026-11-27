import {useEffect, useState} from "react";
import {Link, useParams} from "react-router";
import {api, NotFoundError, TYPE_LABELS, type Profile} from "../api";

export default function ProfilePage() {
    const { id = "" } = useParams();
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

    if (error) {
        return (
            <section>
                <p role="alert">{error}</p>
                <Link to="/">← Back to search</Link>
            </section>
        );
    }

    if (!profile) return <p>Loading…</p>;

    return (
        <section>
            <Link to="/">← Back to search</Link>
            <h1>{profile.name}</h1>
            <p>
                {TYPE_LABELS[profile.type]} · {profile.sector ?? "No sector"} ·{" "}
                {profile.region ?? "No region"}
            </p>
            <p>{profile.description}</p>

            <h2>Skills</h2>
            <p>{profile.skills.join(", ")}</p>

            <h2>Services</h2>
            <p>{profile.services.join(", ")}</p>

            <h2>Looking for</h2>
            <p>{profile.needs.join(", ") || "Nothing listed"}</p>

            <h2>Found on</h2>
            <ul>
                {profile.sources.map((s) => (
                    <li key={s.original_url}>
                        <a href={s.original_url} target="_blank" rel="noreferrer">
                            View on {s.name}
                        </a>
                    </li>
                ))}
            </ul>
        </section>
    );
}
