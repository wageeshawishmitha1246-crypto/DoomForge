import "dotenv/config";
import { network } from "hardhat";

// Addresses are fixed here on purpose: blockchain/.env holds an old Ganache
// ATTESTOR_ADDRESS, and picking that one up is how the wrong attestor got registered.
const CONTRACT_ADDRESS = "0xcd89B1251C942Db70a8A3838d714D994A6AF922B";
const ATTESTOR_ADDRESS = "0xD9ea42010D3491286C545AF5409B438F630821E6";

const { ethers } = await network.connect();

const contract = await ethers.getContractAt("AdaptiveCryptoSecurity", CONTRACT_ADDRESS);

if (await contract.pqAttestors(ATTESTOR_ADDRESS)) {
  console.log("PQ attestor is already registered:", ATTESTOR_ADDRESS);
} else {
  const tx = await contract.setPQAttestor(ATTESTOR_ADDRESS, true);
  await tx.wait();
  console.log("Registered PQ attestor:", ATTESTOR_ADDRESS);
}
console.log("Approved on contract", CONTRACT_ADDRESS, "->", await contract.pqAttestors(ATTESTOR_ADDRESS));
