package avito.innopolis.auth.dto;

import jakarta.validation.constraints.*;


public record UpdateProfileRequest(
        @NotBlank(message = "Укажите имя")
        @Size(max = 100, message = "Имя не должно превышать 100 символов")
        String firstName,
        @NotBlank(message = "Укажите фамилию")
        @Size(max = 100, message = "Фамилия не должна превышать 100 символов")
        String lastName,
        @NotBlank(message = "Укажите электронную почту")
        @Email(message = "Введите корректный адрес электронной почты")
        @Size(max = 255, message = "Адрес электронной почты слишком длинный")
        String email
) {}
