import { onRequestOptions as __api_resume_advanced_js_onRequestOptions } from "E:\\LearnwithHemant\\V110\\functions\\api\\resume-advanced.js"
import { onRequestPost as __api_resume_advanced_js_onRequestPost } from "E:\\LearnwithHemant\\V110\\functions\\api\\resume-advanced.js"
import { onRequestOptions as __api_resume_score_js_onRequestOptions } from "E:\\LearnwithHemant\\V110\\functions\\api\\resume-score.js"
import { onRequestPost as __api_resume_score_js_onRequestPost } from "E:\\LearnwithHemant\\V110\\functions\\api\\resume-score.js"

export const routes = [
    {
      routePath: "/api/resume-advanced",
      mountPath: "/api",
      method: "OPTIONS",
      middlewares: [],
      modules: [__api_resume_advanced_js_onRequestOptions],
    },
  {
      routePath: "/api/resume-advanced",
      mountPath: "/api",
      method: "POST",
      middlewares: [],
      modules: [__api_resume_advanced_js_onRequestPost],
    },
  {
      routePath: "/api/resume-score",
      mountPath: "/api",
      method: "OPTIONS",
      middlewares: [],
      modules: [__api_resume_score_js_onRequestOptions],
    },
  {
      routePath: "/api/resume-score",
      mountPath: "/api",
      method: "POST",
      middlewares: [],
      modules: [__api_resume_score_js_onRequestPost],
    },
  ]