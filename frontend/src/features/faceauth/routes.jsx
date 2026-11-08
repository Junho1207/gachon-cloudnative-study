import Index from "./Index";

export default {
  order: 60,
  nav: [{ to: "/faceauth", label: "얼굴 등록", requiresAuth: true, icon: "home" }],
  routes: [{ path: "/faceauth", element: <Index /> }],
};

