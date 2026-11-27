import {StrictMode} from "react";
import {createRoot} from "react-dom/client";
import {createBrowserRouter, RouterProvider} from "react-router";
import Layout from "./components/Layout";
import SearchPage from "./pages/SearchPage";
import ProfilePage from "./pages/ProfilePage";
import NotFoundPage from "./pages/NotFoundPage";
import "./styles.css";

const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            {
                // Browse view: the list stays on screen while a profile opens beside it.
                element: <SearchPage />,
                children: [
                    {index: true, element: null},
                    {path: "profiles/:id", element: <ProfilePage />},
                ],
            },
            {path: "*", element: <NotFoundPage />},
        ],
    },
]);

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <RouterProvider router={router} />
    </StrictMode>,
);
