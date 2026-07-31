import { useState, useEffect } from "react";

function UserProfile({ userId }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetch(`/api/users/${userId}`)
      .then((res) => res.json())
      .then((data) => setUser(data));
  }, []);

  return (
    <div>
      {user && (
        <ul>
          {user.roles.map((role) => (
            <li>{role}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default UserProfile;
