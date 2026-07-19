import { createRouter, createWebHashHistory } from "vue-router"
import type { RouteRecordRaw } from "vue-router"

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/LoginPage.vue"),
    meta: { guest: true },
  },
  {
    path: "/",
    component: () => import("@/layouts/MainLayout.vue"),
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "Dashboard", component: () => import("@/views/DashboardPage.vue") },
      { path: "chat", name: "Chat", component: () => import("@/views/ChatPage.vue") },
      { path: "files", name: "Files", component: () => import("@/views/FilesPage.vue") },
      { path: "documents", name: "Documents", component: () => import("@/views/DocumentsPage.vue") },
      { path: "documents/:uuid", name: "DocumentDetail", component: () => import("@/views/DocumentDetailPage.vue") },
      { path: "templates", name: "Templates", component: () => import("@/views/TemplatesPage.vue") },
      { path: "statutes", name: "Statutes", component: () => import("@/views/StatutesPage.vue") },
      { path: "search", name: "Search", component: () => import("@/views/SearchPage.vue") },
      { path: "config", name: "Config", component: () => import("@/views/ConfigPage.vue") },
      { path: "logs", name: "Logs", component: () => import("@/views/LogsPage.vue") },
      { path: "tasks", name: "Tasks", component: () => import("@/views/TasksPage.vue") },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// ── 导航守卫:未登录 → /login ──────────────
router.beforeEach((to, _from) => {
  const token = localStorage.getItem("lex_access_token")
  if (to.meta.requiresAuth && !token) {
    return { name: "Login", query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && token) {
    return { name: "Dashboard" }
  }
})

export default router
