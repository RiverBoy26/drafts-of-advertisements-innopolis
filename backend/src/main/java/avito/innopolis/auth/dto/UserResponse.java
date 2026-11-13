package avito.innopolis.auth.dto;

import avito.innopolis.auth.entity.Role;
import avito.innopolis.auth.entity.User;

import java.time.LocalDate;
import java.util.UUID;

public record UserResponse(
        UUID id,
        String firstName,
        String lastName,
        String middleName,
        LocalDate birthDate,
        String email,
        String phone,
        Role role
) {
    public static UserResponse from(User user) {
        return new UserResponse(
                user.getId(),
                user.getFirstName(),
                user.getLastName(),
                user.getMiddleName(),
                user.getBirthDate(),
                user.getEmail(),
                user.getPhone(),
                user.getRole()
        );
    }
}
