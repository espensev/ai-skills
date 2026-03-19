const { getUserData } = require('./userService');

function renderUserProfile(userId) {
    const user = getUserData(userId);
    return `<h1>${user.name}</h1><p>Role: ${user.role}</p>`;
}

module.exports = { renderUserProfile };
