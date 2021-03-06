package com.example.servermanagerapp;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        Button button = findViewById(R.id.button);
        button.setOnClickListener(view -> authenticate());
    }

    public void authenticate() {

        EditText editText = findViewById(R.id.editText);
        EditText portField = findViewById(R.id.portField);
        EditText usernameField = findViewById(R.id.usernameField);
        EditText passwordField = findViewById(R.id.passwordField);

        String host = editText.getText().toString();
        String port = portField.getText().toString();
        String username = usernameField.getText().toString();
        String password = passwordField.getText().toString();

        if(host.trim().length() == 0 || port.trim().length() == 0 || username.trim().length() == 0
                || password.trim().length() == 0) {
            Toast.makeText(getApplicationContext(), "Fill in all of the fields.",
                    Toast.LENGTH_LONG).show();
            return;
        }

        ServerCredentials serverCredentials = new ServerCredentials(host, port, username, password);
        Intent intent = new Intent(this, sshActivity.class);
        intent.putExtra("serverCredentials", serverCredentials);
        this.startActivity(intent);
        finish();
    }
}
