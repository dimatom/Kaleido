import axios from 'axios'

var DevBaseURL = "http://127.0.0.1:8000";

const isDevMode = import.meta.env && import.meta.env.DEV;

var BaseUrl = isDevMode ? DevBaseURL : (window.location.origin);

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

function setCookie(name, value, days) {
    var expires = '';
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
        expires = '; expires=' + date.toUTCString();
    }
    document.cookie = name + '=' + encodeURIComponent(value) + expires + '; path=/';
}

function getCookie(name) {
    var match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    if (match) {
        return decodeURIComponent(match[2]);
    }
    return null;
}

function removeCookie(name) {
    document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
}

function getAccessToken() {
    return getCookie(ACCESS_TOKEN_KEY);
}

function getRefreshToken() {
    return getCookie(REFRESH_TOKEN_KEY);
}

function setTokens(access, refresh) {
    if (access) {
        setCookie(ACCESS_TOKEN_KEY, access, 1);
    }
    if (refresh) {
        setCookie(REFRESH_TOKEN_KEY, refresh, 7);
    }
}

function clearTokens() {
    removeCookie(ACCESS_TOKEN_KEY);
    removeCookie(REFRESH_TOKEN_KEY);
}

const http = axios.create({
    baseURL: BaseUrl
});

http.interceptors.request.use(function (config) {
    var token = getAccessToken();
    if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = 'Bearer ' + token;
    }
    return config;
});

var isRefreshing = false;
var pendingRequests = [];

http.interceptors.response.use(
    function (response) {
        return response;
    },
    async function (error) {
        var original = error.config;
        if (error.response && error.response.status === 401 && original && !original._retry) {
            var refresh = getRefreshToken();
            if (!refresh) {
                clearTokens();
                return Promise.reject(error);
            }
            if (isRefreshing) {
                return new Promise(function (resolve, reject) {
                    pendingRequests.push({ resolve: resolve, reject: reject });
                }).then(function (newAccess) {
                    original.headers = original.headers || {};
                    original.headers.Authorization = 'Bearer ' + newAccess;
                    return http(original);
                });
            }
            original._retry = true;
            isRefreshing = true;
            try {
                var res = await axios.post(BaseUrl + '/token/refresh/', { refresh: refresh });
                var newAccess = res.data.access;
                if (newAccess) {
                    setCookie(ACCESS_TOKEN_KEY, newAccess, 1);
                }
                if (res.data.refresh) {
                    setCookie(REFRESH_TOKEN_KEY, res.data.refresh, 7);
                }
                pendingRequests.forEach(function (p) { p.resolve(newAccess); });
                pendingRequests = [];
                original.headers = original.headers || {};
                original.headers.Authorization = 'Bearer ' + newAccess;
                return http(original);
            } catch (refreshErr) {
                pendingRequests.forEach(function (p) { p.reject(refreshErr); });
                pendingRequests = [];
                clearTokens();
                return Promise.reject(refreshErr);
            } finally {
                isRefreshing = false;
            }
        }
        return Promise.reject(error);
    }
);

function get(url) {
    return http.get(url);
}

function post(url, data) {
    return http.post(url, data);
}

function del(url) {
    return http.delete(url);
}

function opendownload(url) {
    window.open(BaseUrl + url, '_blank');
}

async function downloadWithAuth(url, filename) {
    const response = await fetch(BaseUrl + url, {
        headers: { Authorization: 'Bearer ' + getAccessToken() }
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename || 'download';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
}

function getBaseUrl() {
    return BaseUrl;
}

async function postStream(url, data) {
    var headers = { 'Content-Type': 'application/json' };
    var token = getAccessToken();
    if (token) {
        headers.Authorization = 'Bearer ' + token;
    }
    const response = await fetch(BaseUrl + url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(data)
    });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    return { response, reader, decoder };
}

async function login(username, password) {
    var res = await axios.post(BaseUrl + '/token/', {
        username: username,
        password: password
    });
    var data = res.data || {};
    setTokens(data.access, data.refresh);
    return data;
}

function logout() {
    clearTokens();
}

export default {
    BaseUrl,
    getBaseUrl,
    get,
    post,
    del,
    postStream,
    opendownload,
    downloadWithAuth,
    login,
    logout,
    getAccessToken,
    getRefreshToken,
    setTokens,
    clearTokens
}