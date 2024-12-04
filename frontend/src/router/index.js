import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView/LoginView.vue'
import AnomalyLabelView from "@/views/AnomalyLabelView/AnomalyLabelView.vue";
import Sketch from '@/views/AnomalyLabelView/Sketch/Sketchtest.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/AnomalyLabelView',
      name: 'AnomalyLabelView',
      component: AnomalyLabelView
    },
    {
      path: '/',
      name: 'login',
      component: LoginView
    },
    {
      path:'/Sketch',
      name:'Sketch',
      component:Sketch
    }
  ]
})

export default router
