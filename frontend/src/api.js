import axios from "axios";

const BASE_URL = "";

const getAuthHeader = () => {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const API = {
  user: axios.create({ baseURL: `${BASE_URL}/api/users` }),
  product: axios.create({ baseURL: `${BASE_URL}/api/products` }),
  order: axios.create({ baseURL: `${BASE_URL}/api/orders` }),
  payment: axios.create({ baseURL: `${BASE_URL}/api/payments` }),
};

// Automatically attach JWT token to protected API calls
[API.order, API.payment].forEach((instance) => {
  instance.interceptors.request.use((config) => {
    config.headers = { ...config.headers, ...getAuthHeader() };
    return config;
  });
});

export default API;
