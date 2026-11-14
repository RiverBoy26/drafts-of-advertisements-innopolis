package avito.innopolis.auth.dto;

import avito.innopolis.auth.entity.Role;
import avito.innopolis.auth.entity.User;

import java.util.UUID;

public record UserResponse(
        UUID id,
        String firstName,
        String lastName,
        String email,
        Role role
) {
    public static UserResponse from(User user) {
        return new UserResponse(
                user.getId(),
                user.getFirstName(),
                user.getLastName(),
                user.getEmail(),
                user.getRole()
        );
    }
}
