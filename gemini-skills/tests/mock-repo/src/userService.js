// Legacy user service
function getUserData(userId) {
    return { id: userId, name: "John Doe", role: "admin" };
}

function updateUserData(userId, data) {
    console.log("Updated", userId, data);
    return true;
}

module.exports = { getUserData, updateUserData };
