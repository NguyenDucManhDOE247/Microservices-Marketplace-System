import axios from "axios";

const BASE_URL = "";

const API = {
  user: axios.create({ baseURL: `${BASE_URL}/api/users` }),
  product: axios.create({ baseURL: `${BASE_URL}/api/products` }),
  order: axios.create({ baseURL: `${BASE_URL}/api/orders` }),
  payment: axios.create({ baseURL: `${BASE_URL}/api/payments` }),
};

// Automatically attach JWT token to protected API calls
[API.order, API.payment].forEach((instance) => {
  instance.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  });
});

export default API;
